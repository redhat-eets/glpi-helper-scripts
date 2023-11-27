#!/usr/bin/env python3
"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: compare_sunbird_with_glpi.py                                    |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: Compare Sunbird Inventory with GLPI Inventory                   |
|                                                                              |
|------------------------------------------------------------------------------|
"""
# Imports.
import sys

sys.path.append("../..")
import argparse
import smtplib
from email.message import EmailMessage

import requests
import urllib3
import yaml
from common.sessionhandler import SessionHandler
from common.urlinitialization import UrlInitialization, validate_url
from common.utils import check_fields, print_final_help

# Suppress InsecureRequestWarning caused by REST access without certificate validation.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main() -> None:
    """Main function"""
    # Get the command line arguments from the user.
    parser = argparse.ArgumentParser(
        description="GLPI Computer REST reservation check."
    )
    parser.add_argument(
        "-g",
        "--general_config",
        metavar="general_config",
        help="path to general config YAML file, see general_config_example.yaml",
        required=True,
    )
    parser.add_argument(
        "-i",
        "--ip",
        metavar="ip",
        type=str,
        required=True,
        help='the IP of the GLPI instance (example: "127.0.0.1")',
    )
    parser.add_argument(
        "-t",
        "--token",
        metavar="user_token",
        type=str,
        required=True,
        help="the user token string for authentication with GLPI",
    )
    parser.add_argument(
        "-y",
        "--yaml",
        default=False,
        action="store_true",
        required=False,
        help="a flag for concise output of only the yaml, useful for "
        + "programmatic parsing",
    )
    parser.add_argument(
        "-v",
        "--no_verify",
        action="store_true",
        help="Use this flag if you want to not verify the SSL session if it fails",
    )
    parser.add_argument(
        "-u",
        "--username",
        type=str,
        required=True,
        help="Username of Sunbird service account",
    )
    parser.add_argument(
        "-p",
        "--password",
        type=str,
        required=True,
        help="Password of Sunbird service account",
    )
    parser.add_argument(
        "-s", "--sunbird_url", type=str, required=True, help="URL of Sunbird Instance"
    )
    parser.add_argument(
        "-r",
        "--recipient",
        type=str,
        help="Recipient of email",
    )
    parser.add_argument(
        "-S",
        "--sender",
        type=str,
        help="Sender of email. Address doesn't necessarily need to be valid.",
    )
    parser.add_argument(
        "-e",
        "--email_server",
        type=str,
        help="Server used to send email",
    )
    args = parser.parse_args()

    # Process General Config
    with open(args.general_config, "r") as config_path:
        config_map = yaml.safe_load(config_path)

    user_token = args.token
    ip = args.ip
    global concise
    concise = args.yaml
    no_verify = args.no_verify
    sunbird_username = args.username
    sunbird_password = args.password
    sunbird_url = validate_url(args.sunbird_url)
    email_recipient = args.recipient
    email_sender = args.sender
    email_server = args.email_server
    enable_email = check_email_parameters(email_recipient, email_sender, email_server)

    urls = UrlInitialization(ip)

    with SessionHandler(user_token, urls, no_verify) as session:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        sunbird_machines = get_sunbird_machines(
            config_map, headers, sunbird_url, sunbird_username, sunbird_password
        )

        glpi_machines = get_glpi_machines(session, urls)

        glpi_machines_in_sunbird = get_glpi_machines_in_sunbird(
            glpi_machines, headers, sunbird_url, sunbird_username, sunbird_password
        )

        # Convert keys/serial numbers to upper case
        upper_case_sunbird = [key.upper() for key in sunbird_machines.keys()]
        upper_case_glpi = [key.upper() for key in glpi_machines.keys()]
        upper_case_glpi_in_sunbird = [
            key.upper() for key in glpi_machines_in_sunbird.keys()
        ]

        # Compare the two dictionaries in a case-insensitive manner
        sunbird_only = set(upper_case_sunbird) - set(upper_case_glpi)
        glpi_only = set(upper_case_glpi) - set(upper_case_glpi_in_sunbird)

        # Output the results
        sunbird_only_list = list(sunbird_only)
        glpi_only_list = list(glpi_only)

        output = (
            f"There are {len(sunbird_only_list)} computers in Sunbird but not in GLPI:"
            "\n"
            f"{sunbird_only_list}"
            "\n\n"
            f"There are {len(glpi_only_list)} computers in GLPI but not in Sunbird:"
            "\n"
            f"{glpi_only_list}"
        )

        if enable_email:
            send_email(output, email_recipient, email_sender, email_server)
        print(output)

    if not concise:
        print_final_help()


def get_sunbird_machines(
    config_map: dict, headers: dict, sunbird_url: str, username: str, password: str
) -> dict:
    """Get machines in Sunbird from user-provided locations and cabinets

    Args:
        config_map (dict): a user-provided dictionary of lab locations and cabinets
        headers (dict): headers for API calls to Sunbird
        sunbird_url (str): URL of Sunbird instance
        username (str): Sunbird username
        password (str): Sunbird password

    Returns:
        sunbird_machines (dict): machines in Sunbird from specified locations
    """

    sunbird_machines = {}
    for location in config_map:
        payload = {
            "columns": [
                {"name": "tiSubclass", "filter": {"eq": "Standard"}},
                {"name": "tiClass", "filter": {"eq": "Device"}},
                {"name": "cmbLocation", "filter": {"eq": location}},
                {
                    "name": "cmbCabinet",
                    "filter": {"in": config_map[location]["Cabinets"]},
                },
            ],
            "selectedColumns": [
                {"name": "tiSerialNumber"},
            ],
            "customFieldByLabel": True,
        }

        sunbird_response = requests.post(
            f"{sunbird_url}/api/v2/quicksearch/items",
            headers=headers,
            json=payload,
            verify=False,
            auth=(username, password),
        )
        sunbird_json = sunbird_response.json()["searchResults"]["items"]

        # Only get machines with serial numbers
        machines_with_serial = [
            computer for computer in sunbird_json if "tiSerialNumber" in computer
        ]

        sunbird_dict = {
            computer["tiSerialNumber"]: computer for computer in machines_with_serial
        }
        sunbird_machines.update(sunbird_dict)
    return sunbird_machines


def get_glpi_machines(
    session: requests.sessions.Session, urls: UrlInitialization
) -> dict:
    """Get all machines in GLPI and format them into a dictionary

    Args:
        session (requests.sessions.Session): The requests session object
        urls (UrlInitialization):            The GLPI URLs

    Returns:
        glpi_machines (dict): machines in GLPI
    """
    computers = check_fields(session, urls.COMPUTER_URL)
    computers_list = [yaml.safe_load(computer) for computer in computers]
    glpi_machines = {
        computer["serial"]: computer
        for computer in computers_list
        if computer["serial"]
    }

    return glpi_machines


def get_glpi_machines_in_sunbird(
    glpi_machines: dict, headers: dict, sunbird_url: str, username: str, password: str
) -> dict:
    """Get all machines that are in both GLPI and Sunbird

    Args:
        glpi_machines (dict): All machines that are in GLPI
        headers (dict): headers for API calls to Sunbird
        sunbird_url (str): URL of Sunbird instance
        username (str): Sunbird username
        password (str): Sunbird password

    Returns:
       glpi_machines_in_sunbird (dict): machines that are in both GLPI and Sunbird
    """
    payload = {
        "columns": [
            {"name": "tiSubclass", "filter": {"eq": "Standard"}},
            {"name": "tiClass", "filter": {"eq": "Device"}},
            {"name": "tiSerialNumber", "filter": {"in": list(glpi_machines.keys())}},
        ],
        "selectedColumns": [
            {"name": "tiSerialNumber"},
        ],
        "customFieldByLabel": True,
    }

    computer_response = requests.post(
        f"{sunbird_url}/api/v2/quicksearch/items",
        headers=headers,
        json=payload,
        verify=False,
        auth=(username, password),
    )
    computer_json = computer_response.json()["searchResults"]["items"]
    glpi_machines_in_sunbird = {
        computer["tiSerialNumber"]: computer for computer in computer_json
    }
    return glpi_machines_in_sunbird


def check_email_parameters(
    email_recipient: str, email_sender: str, email_server: str
) -> bool:
    """Determine if all three email parameters are provided or not.
       If only some are provided, raise an error.

    Args:
        email_recipient (str): The address that will receive the email
        email_sender (str):    The address that will send the email
        email_server (str):    The server that will send the email

    Returns:
       bool (bool): True if all three are present, False if all are not present.
    """
    if email_recipient is None and email_sender is None and email_server is None:
        return False
    elif (
        email_recipient is not None
        and email_sender is not None
        and email_server is not None
    ):
        return True
    else:
        raise Exception(
            "In order to send the output via email, you need to define all "
            "three relevant flags (--recipient, --sender, and --email_server)."
            "Alternatively, you can omit all three of these flags if you "
            "don't want to send an email."
        )


def send_email(
    output: str, email_recipient: str, email_sender: str, email_server: str
) -> None:
    """Sends email with relevant information to the specified recipient.

    Args:
        output (str):          Message to send in email
        email_recipient (str): The address that will receive the email
        email_sender (str):    The address that will send the email
        email_server (str):    The server that will send the email
    """

    print(f"Sending Email to {email_recipient}")
    msg = EmailMessage()
    msg.set_content(output)
    msg["Subject"] = "GLPI/Sunbird Comparison"
    msg["From"] = email_sender
    msg["To"] = email_recipient
    s = smtplib.SMTP(email_server)
    s.send_message(msg)
    s.quit()
    print("Email has been sent successfully.")


# Executes main if run as a script.
if __name__ == "__main__":
    main()
