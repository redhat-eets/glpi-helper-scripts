#!/usr/bin/env python3
"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: filter_computers                                                |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: A script to filter the computers in a GLPI instance based on    |
|              resource requirements, and whether they are currently reserved  |
|              (or reservable).                                                |
|                                                                              |
|------------------------------------------------------------------------------|
"""
# Imports.
import sys

sys.path.append("..")
from common.sessionhandler import SessionHandler
from common.urlinitialization import UrlInitialization
from common.utils import (
    check_fields,
    check_field_without_range,
    print_final_help,
)
from common.parser import argparser
import json
import subprocess
from typing import Tuple
import yaml
import operator

# Suppress InsecureRequestWarning caused by REST access without
# certificate validation.
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main() -> None:
    """Main function"""
    # Get the command line arguments from the user.
    parser = argparser()
    parser.parser.description = "GLPI Computer reservation weighted filter."
    parser.parser.add_argument(
        "-l",
        "--list",
        metavar="list",
        type=str,
        required=True,
        help="the path to the yaml file of machine resource requirements: "
        + "core_count,bytes_of_RAM,minimum_disk_space",
    )
    parser.parser.add_argument(
        "-a",
        "--all",
        default=False,
        action="store_true",
        required=False,
        help="a flag to request output of all reservable machines per "
        + "requirement, bypassing the weighted filtering.",
    )

    args = parser.parser.parse_args()
    ip = args.ip
    user_token = args.token
    list = args.list
    no_verify = args.no_verify

    urls = UrlInitialization(ip)

    requirements = parse_list(list)

    reservations = get_reservations(user_token, ip, no_verify)

    with SessionHandler(user_token, urls, no_verify) as session:
        computers = check_fields(session, urls.COMPUTER_URL)
        disks = get_disks(session, urls)
        available, final_choices = reservable(
            session, reservations, computers, disks, requirements
        )

    print_final_decision(available, final_choices, requirements, urls)

    print_final_help()


def parse_list(list: str) -> list:
    """Parse the input requirements yaml file

    Args:
        list (str): the path to the requirements yaml

    Returns:
        requirements (list): the parsed yaml requirements
    """
    print(
        "------------------------------------------------------------------"
        + "--------------\nParsing requirements yaml file\n------------------"
        + "--------------------------------------------------------------"
    )
    requirements = ""
    try:
        f = open(list, "r")
        requirements = yaml.safe_load(f)
        f.close()
    except Exception as e:
        sys.exit("Can't open or parse " + list + ": " + e)

    print("Requirements yaml parsed")
    return requirements


def get_reservations(user_token: str, ip: str, no_verify: bool) -> list:
    """Get the reservations from GLPI

    Args:
        user_token (str): the user's GLPI API token
        ip (str):         the GLPI IP address
        no_verify (bool): if present, this will not verify the SSL session

    Returns:
        parsed_reservations (list): the reservations from GLPI
    """
    print(
        "------------------------------------------------------------------"
        + "--------------\nGetting and parsing reservations\n-----------------"
        + "---------------------------------------------------------------"
    )

    command = ["./check_glpi_reservation.py", "-i", ip, "-t", user_token, "-y"]
    if no_verify:
        command.extend(["-v"])
    reservation_output = subprocess.check_output(command)
    parsed_reservations = yaml.safe_load(reservation_output)

    print("Reservations parsed")
    return parsed_reservations


def get_disks(user_token: str, urls: str) -> list:
    """Get the disks from GLPI

    Args:
        user_token (str):                the user's GLPI API token
        urls (UrlInitialization object): the URL object

    Returns:
        disks (list): the sorted disks from GLPI
    """
    print(
        "------------------------------------------------------------------"
        + "--------------\nGetting disk items\n-----------------"
        + "---------------------------------------------------------------"
    )
    disks = []
    disk_fields = check_fields(user_token, urls.DISK_ITEM_URL)
    for disk_field in disk_fields:
        for disk in disk_field.json():
            disks.append(json.loads(json.dumps(disk)))

    disks.sort(key=operator.itemgetter("totalsize"))
    return disks


def reservable(  # noqa: C901
    user_token: str,
    reservations: list,
    computers: list,
    disks: list,
    requirements: list,
) -> Tuple[dict, dict]:
    """Check for reservable computers, using weighting where able to get as
       close to the requirements as possible

    Args:
        user_token (str):    the user's GLPI API token
        reservations (list): the list of GLPI reservations
        computers (list):    the list of GLPI computers
        disks (list):        the list of GLPI disks
        requirements (list): the list of requirements for reservations

    Returns:
        available (dict):      the dictionary of all choices
        final_choices (dict):  the dictionary of final decisions
    """
    print(
        "------------------------------------------------------------------"
        + "--------------\nChecking for reservable computers\n----------------"
        + "----------------------------------------------------------------"
    )
    available = {}

    total_rounds = len(requirements) * len(computers)
    curr_round = 0
    for requirement in requirements:
        for computer in computers:
            computer = yaml.safe_load(computer)
            cpu_weight = None
            core_weight = None
            memory_weight = None
            gpu = True
            nic = True
            computer_reservable = False
            reservation_free = True

            curr_round += 1
            print(
                "\tProgress: "
                + "{:.2f}".format((curr_round / total_rounds) * 100)
                + "%",
                end="\r",
            )

            # Short circuit for Reservations, as this is where the majority of time
            # goes into filtering
            for link in computer["links"]:
                if link["rel"] == "ReservationItem":
                    computer_reservable = check_computer_reservable(user_token, link)
            if not computer_reservable:
                continue

            for link in computer["links"]:
                if link["rel"] == "Item_DeviceProcessor":
                    cpu_weight = check_cpus(
                        user_token, link, requirements[requirement]["cpu"]
                    )
                    core_weight = check_cores(
                        user_token, link, requirements[requirement]["cores"]
                    )
                    if not (cpu_weight or core_weight):
                        break

                elif link["rel"] == "Item_DeviceMemory":
                    memory_weight = check_memory(
                        user_token, link, requirements[requirement]["ram"]
                    )
                    if not memory_weight:
                        break

                elif (
                    "gpu" in requirements[requirement]
                    and link["rel"] == "Item_DeviceGraphicCard"
                ):
                    gpu = check_graphics(
                        user_token, link, requirements[requirement]["gpu"]
                    )
                elif (
                    "nic" in requirements[requirement]
                    and link["rel"] == "Item_DeviceNetworkCard"
                ):
                    nic = check_network(
                        user_token, link, requirements[requirement]["nic"]
                    )
            if (
                not computer_reservable
                or not (cpu_weight or core_weight)
                or not memory_weight
            ):
                continue

            if "disks" in requirements[requirement]:
                disks_req = requirements[requirement]["disks"]
                disks_req.sort(key=operator.itemgetter("storage"))

                disks_satisfied = check_disks(computer["id"], disks, disks_req)

            if (
                computer_reservable
                and cpu_weight
                and core_weight
                and memory_weight
                and gpu
                and nic
                and disks_satisfied
            ):
                for reservation in reservations:
                    computer_key = "Computer " + str(computer["id"])
                    if computer_key in reservations[reservation]:
                        if (
                            reservations[reservation]["Begins"]
                            <= requirements[requirement]["start"]
                            <= reservations[reservation]["Ends"]
                        ) or (
                            reservations[reservation]["Begins"]
                            <= requirements[requirement]["end"]
                            <= reservations[reservation]["Ends"]
                        ):
                            reservation_free = False
                if reservation_free:
                    total_weight = cpu_weight + core_weight + memory_weight
                    if requirement not in available:
                        available[requirement] = {}
                    if computer["id"] not in available[requirement]:
                        available[requirement][computer["id"]] = {}
                    available[requirement][computer["id"]]["name"] = computer["name"]
                    available[requirement][computer["id"]][
                        "total_weight"
                    ] = total_weight

    sorted_available = {}
    final_choices = {}
    taken_machines = []
    for requirement in available:
        sorted_requirement = sorted(
            available[requirement],
            key=lambda x: (available[requirement][x]["total_weight"]),
        )
        sorted_available[requirement] = sorted_requirement
    for index in range(len(requirements)):
        min = float("inf")
        pick = None
        limited = False
        for requirement in sorted_available:
            if not limited and (len(sorted_available[requirement]) - 1) > index:
                curr = available[requirement][sorted_available[requirement][index]][
                    "total_weight"
                ]
                if curr < min:
                    min = curr
                    pick = requirement
            else:
                if not limited:
                    limited = True
                    min = float("inf")
                for j in range(len(sorted_available[requirement])):
                    curr = available[requirement][sorted_available[requirement][j]][
                        "total_weight"
                    ]
                    if curr < min:
                        min = curr
                        pick = requirement
        if pick is not None:
            for choice in sorted_available[pick]:
                if choice not in taken_machines:
                    taken_machines.append(choice)
                    final_choices[pick] = [choice, available[pick][choice]["name"]]
                    del sorted_available[pick]
                    break
    return available, final_choices


def print_final_decision(
    available: dict, final_choices: dict, requirements: list, urls: UrlInitialization
) -> None:
    """Print the final decisions

    Args:
        available (dict):         the dict of all available machines
        final choices (dict):     the list of decisions for reservable computers
        requirements (list):      the list of original requirements
        urls (UrlInitialization): the URLs
    """
    print(
        "------------------------------------------------------------------"
        + "--------------\nAvailable\n----------------"
        + "----------------------------------------------------------------"
    )
    for requirement in requirements:
        print("requirement: " + str(requirement))
        if requirement in available:
            for computer in available[requirement]:
                print("\tcomputer_id: " + str(computer))
                print("\tcomputer_name: " + available[requirement][computer]["name"])
                print("\tcomputer_link: " + urls.COMPUTER_LINK_URL + str(computer))
        else:
            print("\tcomputer_id: None")
            print("\tcomputer_name: None")
            print("\tcomputer_link: None")
    print(
        "------------------------------------------------------------------"
        + "--------------\nRecommendations\n----------------"
        + "----------------------------------------------------------------"
    )
    all_reserved = True
    for requirement in requirements:
        if requirement in final_choices:
            print("requirement: " + str(requirement))
            print("\tcomputer_id: " + str(final_choices[requirement][0]))
            print("\tcomputer_name: " + final_choices[requirement][1])
            print(
                "\tcomputer_link: "
                + urls.COMPUTER_LINK_URL
                + str(final_choices[requirement][0])
            )

        else:
            print("requirement: " + str(requirement))
            print("\tcomputer_id: None")
            print("\tcomputer_name: None")
            print("\tcomputer_link: None")
            all_reserved = False

    if all_reserved:
        print("fulfilled: true")
    else:
        print("fulfilled: false")


# NOTE: Need to replace this added glpi in the path.
#       Why is that there in the href?
def check_cpus(user_token: str, link: str, req_cpu: int) -> int:
    """Check cpu requirements for a computer

    Args:
        user_token (str): the user's GLPI API token
        link (str):       the GLPI link to the machine to check
        req_cpu (int):    the amount of cpus required

    Returns:
        int:  on success returns the ratio of total cpus to required cpus
        None: otherwise
    """
    cpus = check_field_without_range(user_token, link["href"].replace("/glpi", ""))
    if len(cpus) >= req_cpu:
        return len(cpus) / req_cpu

    return None


def check_cores(user_token: str, link: str, req_cores: int) -> int:
    """Check core requirements for a computer

    Args:
        user_token (str): the user's GLPI API token
        link (str):       the GLPI link to the machine to check
        req_cores (int):  the amount of cores required

    Returns:
        int:  on success returns the ratio of total cores to required cores
        None: otherwise
    """
    cpus = check_field_without_range(user_token, link["href"].replace("/glpi", ""))
    total_cores = 0
    for cpu in cpus:
        total_cores += int(cpu["nbcores"])
    if total_cores >= req_cores:
        return total_cores / req_cores

    return None


def check_memory(user_token: str, link: str, req_memory: int) -> int:
    """Check memory requirements for a computer

    Args:
        user_token (str): the user's GLPI API token
        link (str):       the GLPI link to the machine to check
        req_memory (int): the amount of memory required (MB)

    Returns:
        int:  on success returns the ratio of total ram to required ram
        None: otherwise
    """
    memory = check_field_without_range(user_token, link["href"].replace("/glpi", ""))
    total_ram = 0
    for dimm in memory:
        total_ram += int(dimm["size"])
    if total_ram >= req_memory:
        return total_ram / req_memory

    return None


def check_graphics(user_token: str, link: str, req_gpu: str) -> bool:
    """Check graphics requirements for a computer

    Args:
        user_token (str): the user's GLPI API token
        link (str):       the GLPI link to the machine to check
        req_gpu (str):    the name of the gpu to check

    Returns:
        True: on nic meeting requirements, None otherwise
    """
    graphics = check_field_without_range(user_token, link["href"].replace("/glpi", ""))
    for gpu in graphics:
        for link in gpu["links"]:
            if link["rel"] == "DeviceGraphicCard":
                gpu_info = check_field_without_range(
                    user_token, link["href"].replace("/glpi", "")
                )
                if req_gpu in gpu_info["designation"]:
                    return True

    return None


def check_network(user_token: str, link: str, req_nic: str) -> bool:
    """Check network requirements for a computer

    Args:
        user_token (str): the user's GLPI API token
        link (str):       the GLPI link to the machine to check
        req_nic (str):    the name of the nic to check

    Returns:
        True: on nic meeting requirements, None otherwise
    """
    nics = check_field_without_range(user_token, link["href"].replace("/glpi", ""))
    for nic in nics:
        for link in nic["links"]:
            if link["rel"] == "DeviceNetworkCard":
                nic_info = check_field_without_range(
                    user_token, link["href"].replace("/glpi", "")
                )
                for model_link in nic_info["links"]:
                    if model_link["rel"] == "DeviceNetworkCardModel":
                        model_info = check_field_without_range(
                            user_token, model_link["href"].replace("/glpi", "")
                        )
                        if model_info["name"] and req_nic in model_info["name"]:
                            return True

    return None


def check_disks(computer_id: str, disks: list, req_disks: list) -> bool:
    """Check disk requirements for a computer

    Args:
        computer_id (str): the computer's ID in GLPI
        disks (list):      the list of disks from GLPI
        req_disks (list):  the list of requirements for disks

    Returns:
        True: on disks meeting requirements, False otherwise
    """
    total_disks = 0
    total_storage = 0

    for disk in disks:
        if disk["itemtype"] == "Computer" and disk["items_id"] == computer_id:
            total_storage += int(disk["totalsize"])
            total_disks += 1
            for i in range(len(req_disks)):
                valid_disk = False
                req_disk = req_disks[i]
                if req_disk["storage"] <= int(disk["totalsize"]):
                    if "disk_type" in req_disk:
                        if str(req_disk["disk_type"]) in disk["name"]:
                            valid_disk = True
                    else:
                        valid_disk = True

                if valid_disk:
                    req_disks.pop(i)
                    break

    if req_disks:
        return False
    else:
        return True


def check_computer_reservable(user_token: str, link: str) -> bool:
    """Check that computer is reservable

    Args:
        user_token (str): the user's GLPI API token
        link (str):       the GLPI link to the machine to check

    Returns:
        True: on reservable, False otherwise
    """
    computer_reservable = check_field_without_range(
        user_token, link["href"].replace("/glpi", "")
    )
    if computer_reservable:
        for reservation_info in computer_reservable:
            if reservation_info["is_active"]:
                return True

    return False


# Executes main if run as a script.
if __name__ == "__main__":
    main()
