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
from common.parser import argparser


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
        help="Use this flag if want to overwrite existing names"
    )
    args = parser.parser.parse_args()
    general_config = args.general_config
    user_token = args.token
    list = args.list
    no_dns = args.no_dns
    sku = args.sku
    ip = args.ip
    switch_config = args.switch_config
    no_verify = args.no_verify
    put = args.put
    test = args.experiment
    overwrite = args.overwrite
    parse_list(
        general_config,
        user_token,
        list,
        no_dns,
        sku,
        ip,
        switch_config,
        no_verify,
        put,
        test,
        overwrite
    )


def parse_list(
    general_config: str,
    user_token: str,
    list: str,
    no_dns: str,
    sku: bool,
    ip: str,
    switch_config: str,
    no_verify: bool,
    put: bool,
    experiment: bool,
    overwrite: bool
):
    """Method to create a REST session, getting the session_token and updating
    headers accrodingly. Return the session for further use.

    Args:
        general_config (str): The path to the YAML for the general config
        user_token (str): The user token string for authentication with GLPI
        list (str): The path to the list of machines in the format: ipmi_ip,ipmi_user,
                    ipmi_pass,public_ip,lab
        no_dns (str): Name to use for system instead of hostname or serial number
        sku (bool): Whether or not to use the SKU instead of the serial number of the
                    system
        ip (str): The IP of the GLPI instance
        switch_config (str): The path to the YAML for the switch config
        no_verify (bool): If present, this will not verify the SSL session if it fails,
                          allowing the script to proceed
        put (bool): If present, this will make the script only do PUT requests to GLPI
        experiment (bool): If present, this will append '_TEST' to the serial number of
                           the device
    """
    print("Parsing machine file\n")
    machine_list = ""
    try:
        f = open(list, "r")
        machine_list = f.readlines()
        f.close()
    except FileNotFoundError:
        sys.exit("can't open %s" % (machine_list))

    for line in machine_list:
        if line[0] != "#":
            split_line = line.split(",")
            if len(split_line) == 5:
                print("Calling create_glpi_computer_redfish for line: " + line)
                command = [
                    "./create_glpi_computer_redfish.py",
                    "-g",
                    general_config,
                    "-t",
                    user_token,
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
                    ip,
                ]
                if no_dns:
                    command.extend(["-n", no_dns])
                if sku:
                    command.extend(["-s"])
                if switch_config:
                    command.extend(["-c", switch_config])
                if no_verify:
                    command.extend(["-v"])
                if put:
                    command.extend(["-p"])
                if experiment:
                    command.extend(["-e"])
                if overwrite:
                    command.extend(["-o"])
                output = subprocess.check_output(command)
                print(output.decode("utf-8"))
                print("\n")
            else:
                print("Line formatting incorrect, length is not 5:\n\t")
                print(split_line)

    return


# Executes main if run as a script.
if __name__ == "__main__":
    main()
