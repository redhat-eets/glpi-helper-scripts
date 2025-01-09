#!/usr/bin/env python3
"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: update_accelerators.py                                          |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: Update all accelerators of all machines already in GLPI         |
|                                                                              |
|------------------------------------------------------------------------------|
"""
# Imports.
import sys
import traceback

sys.path.append("..")
from common.sessionhandler import SessionHandler
from common.urlinitialization import UrlInitialization
from common.utils import (
    print_final_help,
    check_fields,
    print_error_table,
    post_accelerators,
)
from common.parser import argparser
from population.create_glpi_computer_redfish import (
    get_accelerators,
    get_processor,
    update_redfish_system_uri,
    get_redfish_system,
)
import redfish
import yaml

# Suppress InsecureRequestWarning caused by REST access to Redfish without
# certificate validation.
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main() -> None:
    """Main function"""
    # Get the command line arguments from the user.
    parser = argparser()
    parser.parser.description = (
        "GLPI Computer REST upload example. NOTE: needs to "
        + "be run with root priviledges."
    )
    parser.parser.add_argument(
        "-g",
        "--general_config",
        metavar="general_config",
        help="path to general config YAML file, see general_config_example.yaml",
        required=True,
    )
    parser.parser.add_argument(
        "-p",
        "--put",
        action="store_true",
        help="Use this flag if you want to only use PUT requests",
    )
    parser.parser.add_argument(
        "-u",
        "--username",
        metavar="username",
        help="Redfish username",
        required=True,
    )
    parser.parser.add_argument(
        "-o",
        "--open_password",
        metavar="open_password",
        help="Password for labs that don't require separate VPN",
        required=True,
    )
    parser.parser.add_argument(
        "-c",
        "--closed_password",
        metavar="closed_password",
        help="Password to use for labs that require separate VPN",
        required=True,
    )
    parser.parser.add_argument(
        "-d",
        "--dry_run",
        action="store_true",
        help="Use this flag if you want to only perform read-only operations",
    )
    parser.parser.add_argument(
        "-f",
        "--file_path",
        metavar="file_path",
        help="Path to output file. If omitted, results will not be saved to file",
    )
    args = parser.parser.parse_args()

    global PUT
    PUT = args.put
    ip = args.ip
    user_token = args.token
    no_verify = args.no_verify
    username = args.username
    closed_password = args.closed_password
    open_password = args.open_password
    dry_run = args.dry_run
    file_path = args.file_path

    # Process General Config
    with open(args.general_config, "r") as config_path:
        config_map = yaml.safe_load(config_path)

    if "ACCELERATOR_IDS" in config_map:
        global ACCELERATOR_IDS
        ACCELERATOR_IDS = config_map["ACCELERATOR_IDS"]

    urls = UrlInitialization(ip)
    error_messages = {}
    with SessionHandler(user_token, urls, no_verify) as session:
        bmc_addresses = check_fields(session, urls.BMC_URL)
        for address in bmc_addresses:
            print(f"Updating accelerators for {address['bmcaddressfield']}")
            if address["bmcaddressfield"].startswith("192.168"):
                password = closed_password
            else:
                password = open_password
            try:
                redfish_base_url = f"https://{address['bmcaddressfield']}"
                redfish_obj = redfish.redfish_client(
                    base_url=redfish_base_url,
                    username=username,
                    password=password,
                    timeout=5,
                    max_retry=2
                )
                redfish_obj.login(auth="session")
                update_redfish_system_uri(redfish_obj, urls)
                system_json = get_redfish_system(redfish_obj)
                processors = get_processor(redfish_obj)
                accelerators = get_accelerators(redfish_obj, system_json, processors)
                try:
                    redfish_obj.logout()
                except redfish.rest.v1.RetriesExhaustedError:
                    print("Unable to logout from Redfish, continuing...")
                    pass
                except redfish.rest.v1.BadRequestError:
                    print("Unable to logout from Redfish, continuing...")
                    pass

                if not dry_run:
                    print(address)
                    post_accelerators(
                        session,
                        urls,
                        accelerators,
                        ACCELERATOR_IDS,
                        address["items_id"],
                    )
                else:
                    print(accelerators)
            except Exception:
                error_message = traceback.format_exc()
                print(error_message)
                error_messages[address["bmcaddressfield"]] = error_message

    print_error_table(error_messages, file_path)
    print_final_help()


# Executes main if run as a script.
if __name__ == "__main__":
    main()
