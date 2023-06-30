#!/usr/bin/env python3
"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: update_switch_ports.py                                          |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: GLPI Switch REST API update implementation for gathering switch |
|              information from lab switches.                                  |
|                                                                              |
|        NOTE: Must be run with root priviledges.                              |
|                                                                              |
|------------------------------------------------------------------------------|
"""
# Imports.
import sys

sys.path.append("..")

import argparse
import pexpect
import requests
from common.sessionhandler import SessionHandler
from common.urlinitialization import UrlInitialization
from common.utils import (
    print_final_help,
    get_switch_ports,
    check_and_post_network_port,
    check_and_post_network_port_ethernet,
)
from common.switches import Switches
from os import getenv


def main() -> None:
    """Main function"""
    # Get the command line arguments from the user.
    parser = argparse.ArgumentParser(
        description="GLPI Switch port REST upload example. NOTE: needs to "
        + "be run with root priviledges."
    )
    parser.add_argument(
        "-i",
        "--ip",
        metavar="ip",
        type=str,
        default=getenv("GLPI_INSTANCE"),
        required=not getenv("GLPI_INSTANCE"),
        help='the IP/URL of the GLPI instance (example: "127.0.0.1")',
    )
    parser.add_argument(
        "-t",
        "--token",
        metavar="user_token",
        type=str,
        default=getenv("GLPI_TOKEN"),
        required=not getenv("GLPI_TOKEN"),
        help="the user token string for authentication with GLPI",
    )
    parser.add_argument(
        "-c",
        "--switch_config",
        metavar="switch_config",
        required=True,
        help="optional path to switch config YAML file",
    )
    args = parser.parse_args()

    user_token = args.token
    ip = args.ip
    switch_config = args.switch_config

    urls = UrlInitialization(ip)
    switch_info = Switches(switch_config)

    with SessionHandler(user_token, urls) as session:
        post_to_glpi(session, urls, switch_info)

    print_final_help()


def post_to_glpi(
    session: requests.sessions.Session, urls: UrlInitialization, switch_info: Switches
) -> None:
    """A method to post the JSON created to GLPI. This method calls numerous helper
       functions which create different parts of the JSON required, get fields from
       GLPI, and post new fields to GLPI when required.

    Args:
        session (Session object): The requests session object
        urls (UrlInitialization object): the URL object
        switch_info (Switches object): Contains information about lab switches
    """
    global switch_dict

    print("Checking GLPI Network Equipment fields:")
    glpi_fields_list = []
    api_range = 0
    api_increment = 50
    more_fields = True
    while more_fields:
        range_url = (
            urls.NETWORK_EQUIPMENT_URL
            + "?range="
            + str(api_range)
            + "-"
            + str(api_range + api_increment)
        )
        glpi_fields = session.get(url=range_url)
        if glpi_fields.json() and glpi_fields.json()[0] == "ERROR_RANGE_EXCEED_TOTAL":
            more_fields = False
        else:
            glpi_fields_list.append(glpi_fields)
            api_range += api_increment

    print("Getting switch information\n")
    for lab in switch_info.switch_map.keys():
        for switch_ip in switch_info.switch_map[lab]["switches"].keys():
            switch_dict = {}
            if "name" in switch_info.switch_map[lab]["switches"][switch_ip]:
                switch_name = switch_info.switch_map[lab]["switches"][switch_ip]["name"]
                print("--------------------\n" + switch_name + "\n--------------------")
                if switch_ip not in switch_dict:
                    switch_dict[switch_ip] = [
                        switch_name,
                        get_switch_ports(lab, switch_ip, switch_info),
                        get_switch_serial(lab, switch_ip, switch_info),
                        get_switch_port_speed(lab, switch_ip, switch_info),
                    ]

                for glpi_fields in glpi_fields_list:
                    for glpi_field in glpi_fields.json():
                        if glpi_field["name"] == switch_name:
                            switch_id = glpi_field["id"]
                            break

                for switch_port_mac in switch_dict[switch_ip][1]:
                    switch_port = switch_dict[switch_ip][1][switch_port_mac]
                    logical_number = switch_port.split()[-1]
                    print(switch_port)
                    if (
                        switch_port[0: len(switch_port) - len(logical_number) - 1]
                        in switch_dict[switch_ip][3]
                    ):
                        speed = switch_dict[switch_ip][3][
                            switch_port[0: len(switch_port) - len(logical_number) - 1]
                        ]
                    else:
                        speed = 0

                    network_port_id = check_and_post_network_port(
                        session,
                        urls.NETWORK_PORT_URL,
                        switch_id,
                        "NetworkEquipment",
                        logical_number,
                        switch_port,
                        "NetworkPortEthernet",
                        None,
                        switch_dict,
                        urls,
                        switch_info,
                    )
                    check_and_post_network_port_ethernet(
                        session,
                        urls.NETWORK_PORT_ETHERNET_URL,
                        network_port_id,
                        speed,
                        None,
                    )
    return


def strip_netshow_interface_switch_speed_dict(dict: str, delimiter: str) -> dict:
    """A helper method to strip whitespace, decode and split a string containing speed
       info generated by a "netshow interface" command.

    Args:
        dict (str): Contains information that needs to be decoded and split into a
                    dictionary
        delimiter (str): Text to split the information on

    Returns:
        stripped_dict (dict): Contains decoded and split information
    """
    stripped_dict = {}
    dict = dict.decode().split("\n")
    for entry in dict:
        temp = entry.lstrip().strip().split(delimiter)
        for item in range(len(temp)):
            temp_split = temp[item].split()
            if temp_split and temp_split[0] == "UP":
                if temp_split[1] in stripped_dict:
                    print("Duplicate: " + temp_split[1])
                if temp_split[2][0] == "(":
                    if temp_split[2][-1] == ")":
                        speed = temp_split[3].split("(")[0]
                    else:
                        speed = temp_split[4].split("(")[0]
                else:
                    speed = temp_split[2].split("(")[0]
                if speed == "N/A":
                    speed = 0
                elif speed[-1] == "G":
                    speed = int(speed[:-1]) * 1000
                else:
                    speed = int(speed[:-1])
                stripped_dict[temp_split[1].split()[0]] = speed
    return stripped_dict


def strip_show_interfaces_status_switch_speed_dict(dict: str, delimiter: str) -> dict:
    """A helper method to strip whitespace, decode and split a string containing speed
       info generated by a "show interfaces status" command.

    Args:
        dict (str): Contains information that needs to be decoded and split into a
                    dictionary
        delimiter (str): Text to split the information on

    Returns:
        stripped_dict (dict): Contains decoded and split information
    """
    # NOTE: This is required because for some switches there seems to be the
    # possibility of multiple macs on single interfaces. My assumption is there
    # is an unmanaged switch or a breakout cable as the culprit.
    # TODO: Follow up on this line of thought to confirm.
    stripped_dict = {}
    dict = dict.decode().split(delimiter)
    for entry in dict:
        temp = entry.lstrip().strip().split()
        if len(temp) >= 7 and temp[-5] == "Up":
            stripped_dict[temp[0] + " " + temp[1]] = temp[-4]

    return stripped_dict


def get_switch_serial(lab: str, switch: str, switch_info: Switches) -> dict:
    """A helper method to get switch serial number via ssh from the switch IP
       address input. After logging into the switch use the global switch command
       and call the stip helper method. Return the dictionary.

    Args:
        lab (str): The lab of the switch
        switch (str): IP address of switch
        switch_info (Switches object): Contains information about lab switches

    Returns:
        switch_output_dict (dict): Dictionary that contains serial number information
    """
    switch_type = switch_info.switch_map[lab]["switches"][switch]["type"].lower()
    terminal_prompt = switch_info.TERMINAL_PROMPT
    if switch_type == "cumulus":
        terminal_prompt += " "
    switch_output_dict = ""
    child = pexpect.spawn(
        "ssh -o StrictHostKeyChecking=no "
        + switch_info.switch_map[lab]["switches"][switch]["username"]
        + "@"
        + switch
    )
    child.expect("password:", timeout=30)
    child.sendline(switch_info.switch_map[lab]["switches"][switch]["password"])
    child.expect(terminal_prompt, timeout=30)
    child.sendline("terminal length 0")
    child.expect(terminal_prompt, timeout=30)
    if switch_type == "cumulus":
        child.sendline(switch_info.DECODE_SYSEEPROM_SWITCH_COMMAND)
        try:
            child.expect("password for cumulus:", timeout=5)
            child.sendline(switch_info.switch_map[lab]["switches"][switch]["password"])
            child.expect(terminal_prompt, timeout=30)
            switch_output_dict = child.after.decode().split()[0]
        except Exception:
            child.expect(terminal_prompt, timeout=30)
            switch_output_dict = child.after.decode().split()[3]
            pass
        child.sendline("$?")
        exit_code = child.after.strip().decode()
        if "127" in exit_code:
            print(
                "Error running command on Cumulus switch: "
                + switch_info.DECODE_SYSEEPROM_SWITCH_COMMAND
            )
    elif switch_type == "dell":
        child.sendline(switch_info.SHOW_SYSTEM_SERICE_TAG_SWITCH_COMMAND)
        child.expect(terminal_prompt, timeout=30)
        switch_output_dict = child.after.strip().split()[-2]
    else:
        print("Switch type unsupported: " + switch_type)
    child.sendline("exit")

    return switch_output_dict


def get_switch_port_speed(lab: str, switch: str, switch_info: Switches) -> dict:
    """A helper method to get switch port speeds via ssh from the switch IP
       address input. After logging into the switch use the global switch command
       and call the stip helper method.

    Args:
        lab (str): The lab of the switch
        switch (str): IP address of the switch
        switch_info (Switches object): Contains information about lab switches

    Returns:
        switch_output_dict (dict): Dictionary that contains speed information
    """
    switch_type = switch_info.switch_map[lab]["switches"][switch]["type"].lower()
    terminal_prompt = switch_info.TERMINAL_PROMPT
    if switch_type == "cumulus":
        terminal_prompt += " "
    switch_output_dict = ""
    child = pexpect.spawn(
        "ssh -o StrictHostKeyChecking=no "
        + switch_info.switch_map[lab]["switches"][switch]["username"]
        + "@"
        + switch
    )
    child.expect("password:", timeout=30)
    child.sendline(switch_info.switch_map[lab]["switches"][switch]["password"])
    child.expect(terminal_prompt, timeout=30)
    if switch_type == "cumulus":
        child.sendline(switch_info.NETSHOW_INTERFACE_SWITCH_COMMAND)
        child.expect(terminal_prompt, timeout=30)
        switch_output_dict = strip_netshow_interface_switch_speed_dict(
            child.after.strip(), "\n"
        )
        child.sendline("$?")
        child.expect(terminal_prompt, timeout=30)
        exit_code = child.after.strip().decode()
        if "127" in exit_code:
            print(
                "Error running command on Cumulus switch: "
                + switch_info.NETSHOW_INTERFACE_SWITCH_COMMAND
            )
    elif switch_type == "dell":
        child.sendline("terminal length 0")
        child.expect(terminal_prompt, timeout=30)
        child.sendline(switch_info.SHOW_INTERFACES_STATUS_SWITCH_COMMAND)
        child.expect(terminal_prompt, timeout=30)
        switch_output_dict = strip_show_interfaces_status_switch_speed_dict(
            child.after.strip(), "\n"
        )
    else:
        print("Switch type unsupported: " + switch_type)
    child.sendline("exit")

    return switch_output_dict


# Executes main if run as a script.
if __name__ == "__main__":
    main()
