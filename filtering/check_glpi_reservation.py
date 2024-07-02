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
from common.sessionhandler import SessionHandler
from common.urlinitialization import UrlInitialization
from common.utils import (
    print_final_help,
    get_reservations,
)
from common.parser import argparser

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
        "-y",
        "--yaml",
        default=False,
        action="store_true",
        required=False,
        help="a flag for concise output of only the yaml, useful for "
        + "programmatic parsing",
    )
    parser.parser.add_argument(
        "-I",
        "--identifier",
        type=str,
        help="Use this flag if you want to list reservations for a specific "
        + "machine identifier",
    )
    parser.parser.add_argument(
        "-u",
        "--user",
        type=str,
        help="Use this flag if you want to list reservations made by a specific user",
    )
    args = parser.parser.parse_args()
    user_token = args.token
    ip = args.ip
    global concise
    concise = args.yaml
    no_verify = args.no_verify
    identifier = args.identifier
    user = args.user
    urls = UrlInitialization(ip)

    with SessionHandler(user_token, urls, no_verify) as session:
        print(get_reservations(session, urls, identifier, user))

    if not concise:
        print_final_help()


# Executes main if run as a script.
if __name__ == "__main__":
    main()
