#!/usr/bin/env python3
"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: filter_reservations_by_project                                  |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: A script to filter the reservations in glpi by project (JIRA    |
|              tag in the comment field), returning all projects with the      |
|              cooresponding tag.                                              |
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
    get_computers,
    get_network_equipment,
    get_reservations,
)
from common.parser import argparser
import yaml
from os import getenv

# Suppress InsecureRequestWarning caused by REST access without
# certificate validation.
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main() -> None:
    """Main function"""
    # Get the command line arguments from the user.
    parser = argparser()
    parser.parser.description="GLPI Computer reservation weighted filter."
    parser.parser.add_argument(
        "-j",
        "--jira",
        metavar="jira_id",
        type=str,
        required=True,
        help="the Jira epic ID associated with the reservation",
    )

    args = parser.parser.parse_args()
    ip = args.ip
    user_token = args.token
    jira = args.jira
    no_verify = args.no_verify

    urls = UrlInitialization(ip)

    with SessionHandler(user_token, urls, no_verify) as session:
        reservations = yaml.safe_load(get_reservations(session, urls))
        computers = get_computers(session, urls)
        network_equipment = get_network_equipment(session, urls)

    get_machines_reserved_with_tag(computers, network_equipment, reservations, jira)

    print_final_help()


def get_machines_reserved_with_tag(
    computers: list, network_equipment: list, reservations: list, jira: str
) -> None:
    """Get the machines reserved with the tag and print reservations

    Args:
        computers (list):    the list of GLPI computers
        reservations (list): the list of GLPI reservations
        jira (str):          the jira tag to match
    """
    print(
        "------------------------------------------------------------------"
        + "--------------\nChecking reserved computer tags\n----------------"
        + "----------------------------------------------------------------"
    )
    for computer in computers:
        computer = yaml.safe_load(computer)
        computer_key = "Computer " + str(computer["id"])
        for reservation in reservations:
            if computer_key in reservations[reservation]:
                reservation_split = reservations[reservation]["Comment"].split()
                if reservation_split:
                    reservation_jira = reservation_split[0]
                    if jira in reservation_jira:
                        print(reservations[reservation])

    for equipment in network_equipment:
        equipment = yaml.safe_load(equipment)
        equipment_key = "NetworkEquipment " + str(equipment["id"])
        for reservation in reservations:
            if equipment_key in reservations[reservation]:
                reservation_split = reservations[reservation]["Comment"].split()
                if reservation_split:
                    reservation_jira = reservation_split[0]
                    if jira in reservation_jira:
                        print(reservations[reservation])

    return


# Executes main if run as a script.
if __name__ == "__main__":
    main()
