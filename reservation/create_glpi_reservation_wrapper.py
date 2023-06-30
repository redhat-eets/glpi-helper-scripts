#!/usr/bin/env python3
"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: create_reservation_wrapper.py                                   |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: Wrapper to upload a list of reservations to GLPI.               |
|                                                                              |
|------------------------------------------------------------------------------|
"""
# Imports.
import subprocess
import sys
import yaml

from common.parser import argparser


def main():
    """Main function"""
    # Get the command line arguments from the user.
    parser = argparser()
    parser.parser.description = "GLPI Computer reservation wrapper."
    parser.parser.add_argument(
        "-l",
        "--list",
        metavar="list",
        type=str,
        required=True,
        help="the path to the yaml file of machines to reserve: ipmi_ip,"
        + "ipmi_user,ipmi_pass,public_ip,{HA or PE}",
    )
    args = parser.parse_args()
    ip = args.ip
    user_token = args.token
    list = args.list

    parse_list(ip, user_token, list)


def parse_list(ip: str, user_token: str, list: str) -> None:
    """Method for parsing the input reservation YAML and calling
       create_glpi_reservation.py.

    Args:
        ip (str):         The IP or hostname of the GLPI session
        user_token (str): The user token to use with GLPI
        list (str):       The YAML file path

    Returns:
        None
    """
    print("Parsing reservation file\n")
    reservations = ""
    try:
        f = open(list, "r")
        reservations = yaml.safe_load(f)
        f.close()
    except OSError:
        sys.exit("can't open or parse %s" % (list))

    for epic in reservations:
        print("Epic: " + epic)
        username = reservations[epic]["username"]
        start = reservations[epic]["start"]
        end = reservations[epic]["end"]
        comment = reservations[epic]["comment"]
        if comment is None:
            comment = ""

        for server in reservations[epic]["servers"]:
            print("\tServer: " + server)
            if reservations[epic]["servers"][server] is not None:
                if (
                    "username" in reservations[epic]["servers"][server]
                    and reservations[epic]["servers"][server]["username"] is not None
                ):
                    username = reservations[epic]["servers"][server]["username"]
                if (
                    "start" in reservations[epic]["servers"][server]
                    and reservations[epic]["servers"][server]["start"] is not None
                ):
                    start = reservations[epic]["servers"][server]["start"]
                if (
                    "end" in reservations[epic]["servers"][server]
                    and reservations[epic]["servers"][server]["end"] is not None
                ):
                    end = reservations[epic]["servers"][server]["end"]
                if (
                    "comment" in reservations[epic]["servers"][server]
                    and reservations[epic]["servers"][server]["comment"] is not None
                ):
                    comment = reservations[epic]["servers"][server]["comment"]

            print("Calling create_glpi_reservation:")
            output = subprocess.check_output(
                [
                    "./create_glpi_reservation",
                    "-i",
                    ip,
                    "-t",
                    user_token,
                    "-u",
                    username,
                    "-b",
                    str(start),
                    "-e",
                    str(end),
                    "-j",
                    epic,
                    "-c",
                    comment,
                    "-s",
                    server,
                ]
            )
            print(output.decode("utf-8"))
            print("\n")

            # Reset potentially overwritten variables.
            username = reservations[epic]["username"]
            start = reservations[epic]["start"]
            end = reservations[epic]["end"]
            comment = reservations[epic]["comment"]
            if comment is None:
                comment = ""

    return


# Executes main if run as a script.
if __name__ == "__main__":
    main()
