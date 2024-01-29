#!/usr/bin/env python3
"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: create_glpi_computer_redfish_wrapper.py                         |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: Wrapper to upload a list of machines to GLPI.                   |
|                                                                              |
|------------------------------------------------------------------------------|
"""
# Imports.
import subprocess
import sys
import argparse

sys.path.append("..")
from common.parser import argparser
from prettytable import PrettyTable


def main():
    """Get the command line arguments from the user."""
    parser = argparser()
    parser.parser.description = "GLPI Computer wrapper."
    parser.parser.add_argument(
        "-g",
        "--general_config",
        metavar="general_config",
        help="path to general config YAML file, see general_config_example.yaml",
        required=True,
    )
    parser.parser.add_argument(
        "-l",
        "--list",
        metavar="list",
        type=str,
        required=True,
        help="the path to the list of machines in the format: ipmi_ip,"
        + "ipmi_user,ipmi_pass,public_ip,lab",
    )
    parser.parser.add_argument(
        "-n",
        "--no_dns",
        metavar="no_dns",
        type=str,
        help="Use this flag if you want to use a custom string as the"
        + "name of this machine instead of using its DNS via nslookup",
    )
    parser.parser.add_argument(
        "-s",
        "--sku",
        action="store_true",
        help="Use this flag if you want to use the SKU of this Dell machine"
        + "instead of its serial number",
    )
    parser.parser.add_argument(
        "-c",
        "--switch_config",
        metavar="switch_config",
        help="path to switch config YAML file",
    )
    parser.parser.add_argument(
        "-e",
        "--experiment",
        action="store_true",
        help="Use this flag if you want to append '_TEST' to the serial number",
    )
    parser.parser.add_argument(
        "-p",
        "--put",
        action="store_true",
        help="Use this flag if you want to only use PUT requests",
    )
    parser.parser.add_argument(
        "-o",
        "--overwrite",
        action="store_true",
        help="Use this flag if want to overwrite existing names",
    )
    parser.parser.add_argument(
        "-U", "--sunbird_username", type=str, help="Username of Sunbird account"
    )
    parser.parser.add_argument(
        "-P", "--sunbird_password", type=str, help="Password of Sunbird account"
    )
    parser.parser.add_argument(
        "-S", "--sunbird_url", type=str, help="URL of Sunbird instance"
    )
    parser.parser.add_argument(
        "-C",
        "--sunbird_config",
        metavar="sunbird_config",
        help="path to sunbird config YAML file, see "
        + "integration/sunbird/example_sunbird.yml",
    )
    args = parser.parser.parse_args()
    parse_list(args)


def parse_list(args: argparse.Namespace):
    """Method to create a REST session, getting the session_token and updating
    headers accrodingly. Return the session for further use.

    Args:
        args (argparse.Namespace): Arguments passed in by the user via the CLI
    """
    print("Parsing machine file\n")
    machine_list = ""
    try:
        f = open(args.list, "r")
        machine_list = f.readlines()
        f.close()
    except FileNotFoundError:
        sys.exit("can't open %s" % (machine_list))

    error_messages = {}
    for line in machine_list:
        if line[0] != "#":
            split_line = line.split(",")
            if len(split_line) == 5:
                print("Calling create_glpi_computer_redfish for line: " + line)
                command = build_command(split_line, args)
                try:
                    output = subprocess.check_output(command, stderr=subprocess.STDOUT)
                    print(output.decode("utf-8"))
                    print("\n")
                except subprocess.CalledProcessError as e:
                    # Capture the error message and add it to the list
                    full_error = e.output.decode().strip()
                    print("Error:", full_error)
                    error_messages[split_line[0].strip()] = full_error.splitlines()[-1]
                print("\n")
            else:
                print("Line formatting incorrect, length is not 5:\n\t")
                print(split_line)
    print_error_table(error_messages)
    return


def build_command(split_line: list, args: argparse.Namespace) -> list:
    """Method to create a REST session, getting the session_token and updating
    headers accrodingly. Return the session for further use.

    Args:
        split_line (list): Information about a machine, split into a list
        args (argparse.Namespace): Arguments passed in by the user via the CLI
    """
    command = [
        "./create_glpi_computer_redfish.py",
        "-g",
        args.general_config,
        "-t",
        args.token,
        "--ipmi_ip",
        split_line[0].strip(),
        "--ipmi_user",
        split_line[1].strip(),
        "--ipmi_pass",
        split_line[2].strip(),
        "--public_ip",
        split_line[3].strip(),
        "--lab",
        split_line[4].strip(),
        "-i",
        args.ip,
    ]
    if args.no_dns:
        command.extend(["-n", args.no_dns])
    if args.sku:
        command.extend(["-s"])
    if args.switch_config:
        command.extend(["-c", args.switch_config])
    if args.no_verify:
        command.extend(["-v"])
    if args.put:
        command.extend(["-p"])
    if args.experiment:
        command.extend(["-e"])
    if args.overwrite:
        command.extend(["-o"])
    if args.sunbird_username and args.sunbird_password and args.sunbird_url:
        command.extend(
            [
                "-U",
                args.sunbird_username,
                "-P",
                args.sunbird_password,
                "-S",
                args.sunbird_url,
            ]
        )
    if args.sunbird_config:
        command.extend(["-C", args.sunbird_config])
    return command


def print_error_table(error_messages: dict) -> None:
    """Takes errors generated by imports and prints formatted table with BMC IP's
    and their corresponding errors.

    Args:
        error_messages (dict[str, str]): Dictionary of BMC IP's and their errors
    """
    if error_messages:
        table = PrettyTable()
        table.field_names = ["BMC IP", "Error Message"]
        for error in error_messages:
            table.add_row([error, error_messages[error]])
        print(table)
    else:
        print("No errors detected!")
        print("\n")


# Executes main if run as a script.
if __name__ == "__main__":
    main()
