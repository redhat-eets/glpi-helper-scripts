#!/usr/bin/env python3
"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: check_glpi_reservation.py                                       |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: GLPI Computer REST API reservation checks.                      |
|                                                                              |
|------------------------------------------------------------------------------|
"""
# Imports.
import sys

sys.path.append("..")
import argparse
from common.sessionhandler import SessionHandler
from common.urlinitialization import UrlInitialization
from common.utils import (
    print_final_help,
    get_reservations,
)

# Suppress InsecureRequestWarning caused by REST access without
# certificate validation.
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main() -> None:
    """Main function"""
    # Get the command line arguments from the user.
    parser = argparse.ArgumentParser(
        description="GLPI Computer REST reservation check."
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

    args = parser.parse_args()
    user_token = args.token
    ip = args.ip
    global concise
    concise = args.yaml
    no_verify = args.no_verify

    urls = UrlInitialization(ip)

    session_object = SessionHandler(user_token, urls.INIT_URL, urls.KILL_URL, no_verify)
    session = session_object.session

    print(get_reservations(session, urls))

    del session_object

    if not concise:
        print_final_help()


# Executes main if run as a script.
if __name__ == "__main__":
    main()
