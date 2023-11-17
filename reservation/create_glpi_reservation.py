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

from common.parser import argparser
from common.sessionhandler import SessionHandler
from common.urlinitialization import UrlInitialization
from common.utils import (
    check_field,
    error,
    print_final_help,
)


def main() -> None:
    """Main function"""
    # Get the command line arguments from the user.
    parser = argparser()
    parser.parser.description = "GLPI Computer REST reservation check."
    parser.parser.add_argument(
        "-u",
        "--user",
        metavar="username",
        type=str,
        required=True,
        help="the username string associated with the reservation",
    )
    parser.parser.add_argument(
        "-b",
        "--begin",
        metavar="begin",
        type=str,
        required=True,
        help="the beginning time associated with the reservation in "
        + 'format "YYYY-MM-DD HH:MM:SS"',
    )
    parser.parser.add_argument(
        "-e",
        "--end",
        metavar="end",
        type=str,
        required=True,
        help="the ending time associated with the reservation in "
        + 'format "YYYY-MM-DD HH:MM:SS"',
    )
    parser.parser.add_argument(
        "-j",
        "--jira",
        metavar="jira_id",
        type=str,
        required=False,
        help="the Jira epic ID associated with the reservation",
    )
    parser.parser.add_argument(
        "-c",
        "--comment",
        metavar="comment",
        type=str,
        required=False,
        help="a comment appended to the Jira epic ID to be associated with "
        + "the reservation",
    )
    parser.parser.add_argument(
        "-s",
        "--server",
        metavar="hostname",
        type=str,
        required=True,
        help="the fully qualified hostname of the server associated with the "
        + " reservation (for instance "
        + '"machine.example.com")',
    )
    args = parser.parser.parse_args()
    ip = args.ip
    user_token = args.token
    username = args.user
    begin = args.begin
    end = args.end
    jira_id = args.jira
    comment = args.comment
    hostname = args.server

    if jira_id:
        final_comment = jira_id
    else:
        final_comment = ""
    if comment:
        final_comment += "\n" + comment

    urls = UrlInitialization(ip)

    with SessionHandler(user_token, urls) as session:
        create_reservations(
            session, username, hostname, begin, end, final_comment, urls
        )

    print_final_help()


def create_reservations(
    session: requests.sessions.Session,
    username: str,
    hostname: str,
    begin: str,
    end: str,
    final_comment: str,
    urls: UrlInitialization,
) -> None:
    """Method for creating GLPI reservations

    Args:
        session (Session object): The requests session object
        url (str): The url to get the fields

    Returns:
        glpi_fields (list[json]): The glpi fields at the URL
    """
    print("Creating reservation:\n")

    user_id = check_field(session, urls.USER_URL, {"name": username})
    if user_id is None:
        error("User " + username + " is not present.")

    computer_id = check_field(session, urls.COMPUTER_URL, {"name": hostname})
    if computer_id is None:
        error("Computer " + hostname + " is not present.")

    reservation_item_id = check_reservation_item(
        session, urls.RESERVATION_ITEM_URL, "Computer", computer_id
    )
    if reservation_item_id is None:
        error("Computer " + hostname + " is not reservable.")

    reservation_id = post_reservation(
        session,
        urls.RESERVATION_URL,
        reservation_item_id,
        begin,
        end,
        user_id,
        final_comment,
    )
    if reservation_id is False:
        error(
            "Unable to reserve "
            + hostname
            + " for "
            + username
            + ". This "
            + "machine is likely already reserved in this timeframe. Please "
            + "check GLPI."
        )
    return


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
        (str): The reservation id if created, None otherwise
    """
    # Create a field if one was not found and return the ID.
    print("Creating GLPI Reservation Item field:")
    glpi_post = {
        "reservationitems_id": reservation_id,
        "begin": begin,
        "end": end,
        "users_id": user_id,
        "comment": final_comment,
    }

    post_response = session.post(url=url, json={"input": glpi_post})
    print(str(post_response) + "\n")
    response_code = str(post_response)[-5:-2]
    if response_code != "200" and response_code != "201":
        return False

    return post_response.json()["id"]


# Executes main if run as a script.
if __name__ == "__main__":
    main()
