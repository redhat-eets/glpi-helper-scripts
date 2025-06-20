#!/usr/bin/env python3
"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: create_glpi_reservation.py                                      |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: GLPI Computer REST API reservation creation.                    |
|                                                                              |
|------------------------------------------------------------------------------|
"""
# Imports.
import sys

sys.path.append("..")
import requests
import yaml

from common.parser import argparser
from common.sessionhandler import SessionHandler
from common.urlinitialization import UrlInitialization
from common.utils import check_field, error, print_final_help, print_error_table

# Suppress InsecureRequestWarning caused by REST access without
# certificate validation.
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main() -> None:
    """Main function"""
    # Get the command line arguments from the user.
    parser = argparser()
    parser.parser.description = "GLPI Computer REST reservation check."
    parser.parser.add_argument(
        "-l",
        "--list",
        metavar="list",
        type=str,
        required=True,
        help="the path to the yaml file of machines to reserve",
    )

    args = parser.parser.parse_args()
    ip = args.ip
    user_token = args.token
    no_verify = args.no_verify
    reservation_list = args.list
    urls = UrlInitialization(ip)

    with SessionHandler(user_token, urls, no_verify) as session:
        parse_list(session, reservation_list, urls)

    print_final_help()


def parse_list(
    session: requests.sessions.Session, list: str, urls: UrlInitialization
) -> None:
    """Method for parsing the input reservation YAML and creating reservations

    Args:
        session (Session object): The requests session object
        list (str):               The YAML file path
        urls (UrlInitialization): The GLPI URLs
    Returns:
        None
    """
    print("Parsing reservation file\n")
    error_messages = {}
    try:
        f = open(list, "r")
        reservations = yaml.safe_load(f)
        f.close()
    except OSError:
        sys.exit("can't open or parse %s" % (list))

    username = reservations.get("username")
    start = reservations.get("start")
    end = reservations.get("end")
    comment = reservations.get("comment", "") or ""
    epic = reservations.get("jira", "")

    for server in reservations["servers"]:
        print("\tServer: " + server)
        if reservations["servers"][server] is not None:
            if (
                "username" in reservations["servers"][server]
                and reservations["servers"][server]["username"] is not None
            ):
                username = reservations["servers"][server]["username"]
            if (
                "start" in reservations["servers"][server]
                and reservations["servers"][server]["start"] is not None
            ):
                start = reservations["servers"][server]["start"]
            if (
                "end" in reservations["servers"][server]
                and reservations["servers"][server]["end"] is not None
            ):
                end = reservations["servers"][server]["end"]
            if (
                "comment" in reservations["servers"][server]
                and reservations["servers"][server]["comment"] is not None
            ):
                comment = reservations["servers"][server]["comment"]
            if (
                "epic" in reservations["servers"][server]
                and reservations["servers"][server]["epic"] is not None
            ):
                epic = reservations["servers"][server]["epic"]
        if epic:
            final_comment = epic
        else:
            final_comment = ""
        if comment:
            final_comment += "\n" + comment
        if username is None or server is None or start is None or end is None:
            raise KeyError(
                (
                    "You need to specify a username, server name, start date,"
                    " and end date, either globally or for each machine."
                )
            )
        print("Calling create_reservation:")
        error_message = create_reservations(
            session, username, server, start, end, final_comment, urls
        )

        if error_message is not None:
            error_messages[server] = f"({username}) {error_message}"
        # Reset potentially overwritten variables.
        username = reservations["username"]
        start = reservations["start"]
        end = reservations["end"]
        comment = reservations.get("comment") or ""
        epic = reservations.get("jira", "")
    print_error_table(error_messages)


def create_reservations(
    session: requests.sessions.Session,
    username: str,
    identifier: str,
    begin: str,
    end: str,
    final_comment: str,
    urls: UrlInitialization,
) -> str:
    """Method for creating GLPI reservations

    Args:
        session (Session object): The requests session object
        username (str):           The username to use with the reservation
        identifier (str):         The name of the machine to reserver
        begin (str):              The start date of the reservation
        end (str):                The end date of the reservation
        final_comment (str):      The comment to apply to the reservation
        urls (UrlInitialization): The GLPI URLs

    Returns:
        error_message (str): The error returned if reservation creation fails.
    """
    print("Creating reservation:\n")

    user_id = check_field(session, urls.USER_URL, {"name": username})
    if user_id is None:
        error("User " + username + " is not present.")

    computer_id = check_field(session, urls.COMPUTER_URL, {"name": identifier})
    if computer_id is None:
        error("Computer " + identifier + " is not present.")

    reservation_item_id = check_reservation_item(
        session, urls.RESERVATION_ITEM_URL, "Computer", computer_id
    )
    if reservation_item_id is None:
        error("Computer " + identifier + " is not reservable.")

    error_message = post_reservation(
        session,
        urls.RESERVATION_URL,
        reservation_item_id,
        begin,
        end,
        user_id,
        final_comment,
    )
    if error_message is not None:
        print(f"Unable to reserve {identifier} for {username}.")
    else:
        print(f"{identifier} was reserved for {username}.")

    return error_message


def check_reservation_item(
    session: requests.sessions.Session,
    url: str,
    item_type: str,
    item_id: str,
) -> str:
    """Method for checking a reservation item exists.

    Args:
        session (Session object): The requests session object
        url (str):                The URL
        item_type (str):          The type of the reservation
        item_id (str):            The id of the reservation

    Returns:
        (str): The field ID if found, None otherwise
    """
    # Check if the field is present at the URL endpoint.
    print("Checking GLPI Reservation fields:")
    id = check_field(
        session, url, search_criteria={"items_id": item_id, "itemtype": item_type}
    )
    return id


def post_reservation(
    session: requests.sessions.Session,
    url: str,
    reservation_id: str,
    begin: str,
    end: str,
    user_id: str,
    final_comment: str,
) -> str:
    """Method for posting a reservation item.

    Args:
        session (Session object): The requests session object
        url (str):                The URL
        reservation_id (str):     The id of the reservation
        begin (str):              The formatted beginning time
        end (str):                The formatted end time
        user_id (str):            The id of the user for reservation
        final_comment (str):      The comment for the reservation

    Returns:
        (str): The error message if created, None otherwise
    """
    # Create a field if one was not found and return the ID.
    print("Creating GLPI Reservation Item field:")
    glpi_post = {
        "reservationitems_id": reservation_id,
        "begin": str(begin),
        "end": str(end),
        "users_id": user_id,
        "comment": final_comment,
    }

    post_response = session.post(url=url, json={"input": glpi_post})
    print(str(post_response) + "\n")
    if post_response.status_code not in (200, 201):
        return f"{post_response.status_code}: {post_response.text}"


# Executes main if run as a script.
if __name__ == "__main__":
    main()
