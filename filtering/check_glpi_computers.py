#!/usr/bin/env python3
"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: check_glpi_computers.py                                         |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: GLPI Computer REST API checks.                                  |
|                                                                              |
|------------------------------------------------------------------------------|
"""
# Imports.
import sys

sys.path.append("..")
import argparse
from common.sessionhandler import SessionHandler
from common.urlinitialization import UrlInitialization
from common.utils import print_final_help, get_computers
from common.parser import argparser

# Suppress InsecureRequestWarning caused by REST access without
# certificate validation.
import urllib3

from os import getenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main() -> None:
    """Main function"""
    # Get the command line arguments from the user.
    parser = argparser()
    parser.parser.description = "GLPI Computer REST reservation check."
    parser.parser.add_argument(
        "-c",
        "--concise",
        default=False,
        action="store_true",
        required=False,
        help="a flag for concise output of only the yaml, useful for "
        + "programmatic parsing",
    )
    args = parser.parser.parse_args()
    ip = args.ip
    user_token = args.token
    global concise
    concise = args.concise
    no_verify = args.no_verify

    urls = UrlInitialization(ip)

    with SessionHandler(user_token, urls, no_verify) as session:
        print(get_computers(session, urls))

    if not concise:
        print_final_help()
    



# Executes main if run as a script.
if __name__ == "__main__":
    main()
