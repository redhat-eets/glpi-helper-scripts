#!/usr/bin/env python3
"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: create_glpi_computer_coreos.py                                  |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: GLPI Computer REST API Computer upload/update implementation    |
|              modified for gathering server information on CoreOS. The        |
|              intention is to avoid OS commands in the normal                 |
|              create_glpi_computer.py which are unavailable on CoreOS.        |
|                                                                              |
|------------------------------------------------------------------------------|
"""
# Imports.
import sys

sys.path.append("..")
import pexpect
import requests
from common.utils import (
    print_final_help,
    check_and_post,
    check_and_post_processor,
    check_and_post_processor_item,
    check_and_post_network_port,
    check_and_post_device_memory_item,
    check_fields,
)
import common.format_dicts as format_dicts
from common.sessionhandler import SessionHandler
from common.urlinitialization import UrlInitialization
from common.switches import Switches
from common.parser import argparser


def main() -> None:
    """Main function"""
    # Get the command line arguments from the user.
    parser = argparser()
    parser.parser.description = (
        "GLPI Computer REST upload example. NOTE: needs to "
        + "be run with root priviledges."
    )
    parser.parser.add_argument(
        "-rsa",
        "--rsa_path",
        metavar="rsa_key_path",
        type=str,
        required=False,
        help="the path to the rsa key for ssh into the CoreOS node",
    )
    parser.parser.add_argument(
        "-userver",
        "--username_server",
        metavar="server_username",
        type=str,
        required=True,
        help="the username of the CoreOS node",
    )
    parser.parser.add_argument(
        "-ipserver",
        "--ip_server",
        metavar="server_ip",
        type=str,
        required=True,
        help="the ip of the CoreOS node",
    )
    parser.parser.add_argument(
        "-c",
        "--switch_config",
        metavar="switch_config",
        help="optional path to switch config YAML file",
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
        help="Use this flag if you want to overwrite existing names",
    )
    args = parser.parser.parse_args()

    user_token = args.token
    rsa_key = args.rsa_path
    server_username = args.username_server
    server_ip = args.ip_server
    ip = args.ip
    switch_config = args.switch_config
    no_verify = args.no_verify
    global TEST
    TEST = args.experiment
    global PUT
    PUT = args.put
    overwrite = args.overwrite

    urls = UrlInitialization(ip)
    switch_info = Switches(switch_config)

    with SessionHandler(user_token, urls, no_verify) as session:
        post_to_glpi(
            session, rsa_key, server_username, server_ip, urls, switch_info, overwrite
        )

    print_final_help()


# This method takes the GLPI
# REST session and returns when complete.
def post_to_glpi(  # noqa: C901
    session: requests.sessions.Session,
    rsa_key: str,
    server_username: str,
    server_ip: str,
    urls: UrlInitialization,
    switch_info: Switches,
    overwrite: bool,
) -> None:
    """A method to post the JSON created to GLPI. This method calls numerous helper
       functions which create different parts of the JSON required, get fields from
       GLPI, and post new fields to GLPI when required.

    Args:
        session (Session object): The requests session object
        rsa_key (str): The path to the rsa key for sshing into the CoreOS node
        server_username (str): The username of the CoreOS node
        server_ip (str): The ip of the CoreOS node
        urls (UrlInitialization object): the URL object
        switch_info (Switches object): Contains information about lab switches
        overwrite (bool): Flagged to overwrite existing names
    """
    print("Getting machine information\n")
    ssh_command = "ssh -o StrictHostKeyChecking=no "
    if rsa_key:
        ssh_command += "-i " + rsa_key + " "
    child = pexpect.spawn(ssh_command + server_username + "@" + server_ip)
    child.expect(".*\$ ", timeout=30)  # noqa: W605
    child.sendline("sudo hostnamectl")
    child.expect(".*\$ ", timeout=30)  # noqa: W605
    # Get the hostnamectl output as an example, splitting on newlines.
    hostnamectl_output = child.after.splitlines()
    # Get the serial number of the machine.
    child.sendline("sudo cat /sys/devices/virtual/dmi/id/product_serial")
    child.expect(".*\$ ", timeout=30)  # noqa: W605
    serial_number = child.after.strip().decode().split("\r\n")[1]
    # Append TEST to the serial number if the TEST flag is set.
    if TEST:
        serial_number = serial_number + "_TEST"
    # Get the manufacturer of the machine.
    child.sendline("sudo cat /sys/devices/virtual/dmi/id/sys_vendor")
    child.expect(".*\$ ", timeout=30)  # noqa: W605
    computer_type = child.after.strip().decode().split("\r\n")[1]
    # Get the model of the machine.
    child.sendline("sudo cat /sys/devices/virtual/dmi/id/product_name")
    child.expect(".*\$ ", timeout=30)  # noqa: W605
    computer_model = child.after.strip().decode().split("\r\n")[1]
    # Get the uuid.
    child.sendline("sudo cat /sys/devices/virtual/dmi/id/product_uuid")
    child.expect(".*\$ ", timeout=30)  # noqa: W605
    uuid = child.after.strip().decode().split("\r\n")[1]
    # Get the processor(s).
    child.sendline("sudo lscpu")
    child.expect(".*\$ ", timeout=30)  # noqa: W605
    lscpu_output = child.after.splitlines()
    # Get the OS.
    child.sendline("sudo cat /etc/os-release")
    child.expect(".*\$ ", timeout=30)  # noqa: W605
    os = child.after.strip().decode()
    # Get the kernel version.
    child.sendline("sudo uname -r")
    child.expect(".*\$ ", timeout=30)  # noqa: W605
    kernel = child.after.strip().decode().split("\r\n")[1]
    # Get the architecure version.
    child.sendline("sudo uname -m")
    child.expect(".*\$ ", timeout=30)  # noqa: W605
    architecture = child.after.strip().decode().split("\r\n")[1]
    # Get all interfaces.
    child.sendline("sudo ifconfig")
    child.expect(".*\$ ", timeout=30)  # noqa: W605
    networks = child.after.strip().decode()
    # Get RAM information.
    child.sendline(
        'sudo awk \'$3=="kB"{$2=$2/1024;$3="MB"} 1\' /proc/meminfo | column -t'
    )
    child.expect(".*\$ ", timeout=30)  # noqa: W605
    ram = child.after.strip().decode()
    # Get volume information.
    child.sendline("sudo lsblk")
    child.expect(".*\$ ", timeout=30)  # noqa: W605
    disks = child.after.strip().decode()
    # Get NIC information.
    child.sendline(
        "sudo ls -l /sys/class/net | grep pci | rev | cut -d'/' -f1 | rev| xargs -n1 "
        + "ip a show dev"
    )
    child.expect(".*\$ ", timeout=30)  # noqa: W605
    nics = child.after.strip().decode()

    # Strip leading whitespace and create dictionaries of the entries.
    hostnamectl_dict = format_dicts.strip_dict(hostnamectl_output, ": ")
    cpu_dict = format_dicts.strip_dict(lscpu_output, ": ")
    os_dict = format_dicts.strip_decoded_dict(os, "=")
    networks_dict = format_dicts.strip_network_dict(networks, ": ", True)
    ram_dict = format_dicts.strip_ram_dict_coreos(ram, ": ")
    disk_dict = format_dicts.strip_disks_dict_coreos(disks, "\n")
    nics_dict = format_dicts.strip_nics_dict_coreos(nics, "\n", ": <", child)

    # Call helper functions to check fields present in GLPI for the various
    # machine fields to be populated and post them to GLPI if necessary.
    #
    # NOTE: Different helper functions exist because of different syntax,
    #       field names, and formatting in the API.
    computer_type_id = check_and_post(
        session,
        urls.COMPUTER_TYPE_URL,
        {"name": hostnamectl_dict["Chassis"].capitalize()},
    )
    manufacturers_id = check_and_post(
        session, urls.MANUFACTURER_URL, {"name": computer_type}
    )
    computer_model_id = check_and_post(
        session, urls.COMPUTER_MODEL_URL, {"name": computer_model}
    )
    processors_id = check_and_post_processor(session, cpu_dict, urls.CPU_URL, urls)
    operating_system_id = check_and_post(
        session, urls.OPERATING_SYSTEM_URL, {"name": os_dict["NAME"]}
    )
    operating_system_version_id = check_and_post(
        session, urls.OPERATING_SYSTEM_VERSION_URL, {"name": os_dict["VERSION"]}
    )
    operating_system_architecture_id = check_and_post(
        session, urls.OPERATING_SYSTEM_ARCHITECTURE_URL, {"name": architecture}
    )
    operating_system_kernel_version_id = check_and_post(
        session, urls.OPERATING_SYSTEM_KERNEL_VERSION_URL, {"name": kernel}
    )

    # The final dictionary for the machine JSON to post.
    glpi_post = {}
    # Add the computer name.
    if "Transient hostname" in hostnamectl_dict:
        glpi_post["name"] = hostnamectl_dict["Transient hostname"]
    else:
        glpi_post["name"] = hostnamectl_dict["Static hostname"]

    # Add the computer serial number.
    glpi_post["serial"] = serial_number
    # Add the computer type.
    glpi_post["computertypes_id"] = computer_type_id
    # Add the computer manufacturer.
    glpi_post["manufacturers_id"] = manufacturers_id
    # Add the computer model.
    glpi_post["computermodels_id"] = computer_model_id
    # Add the system uuid.
    glpi_post["uuid"] = uuid

    # Get the list of computers and check the serial number. If the serial
    # number matches then use a PUT to modify the cooresponding computer by ID.
    glpi_fields_list = check_fields(session, urls.COMPUTER_URL)

    for glpi_computer in glpi_fields_list:
        if glpi_computer["serial"] == serial_number:
            global PUT
            global COMPUTER_ID
            PUT = True
            COMPUTER_ID = glpi_computer["id"]
            if glpi_computer["name"] != glpi_post["name"] and not overwrite:
                glpi_post["name"] = glpi_computer["name"]
            break

    # If the PUT flag is set then PUT the data to GLPI to modify the existing
    # machine, otherwise POST it to create a new machine.
    print("Sending JSON to GLPI server:")
    if PUT:
        computer_response = session.put(
            url=urls.COMPUTER_URL + str(COMPUTER_ID), json={"input": glpi_post}
        )
        print(str(computer_response) + "\n")
    else:
        computer_response = session.post(
            url=urls.COMPUTER_URL, json={"input": glpi_post}
        )
        print(str(computer_response) + "\n")
        COMPUTER_ID = computer_response.json()["id"]

    # NOTE: The 'check_and_post' style helper methods called below (for the
    # processor(s), operating system, switches, memory, and network) come after
    # the PUT/POST of the machine itself because they require the computer's ID.
    check_and_post_processor_item(
        session,
        cpu_dict,
        urls.CPU_ITEM_URL,
        COMPUTER_ID,
        processors_id,
        "Computer",
        int(cpu_dict["Socket(s)"]),
    )

    check_and_post(
        session,
        urls.OPERATING_SYSTEM_ITEM_URL,
        {
            "items_id": COMPUTER_ID,
            "itemtype": "Computer",
            "operatingsystems_id": operating_system_id,
        },
        {
            "operatingsystemversions_id": operating_system_version_id,
            "operatingsystemarchitectures_id": operating_system_architecture_id,
            "operatingsystemkernelversions_id": operating_system_kernel_version_id,
        },
    )
    # Create network devices.
    nic_ids = {}
    for name in nics_dict:
        bandwidth = ""
        if "capacity" in nics_dict[name]:
            bandwidth = nics_dict[name]["capacity"]

        nic_model_id = 0
        if "product" in nics_dict[name]:
            nic_model_id = check_and_post(
                session,
                urls.DEVICE_NETWORK_CARD_MODEL_URL,
                {"name": nics_dict[name]["product"]},
            )

        vendor = 0
        if "vendor" in nics_dict[name]:
            vendor = nics_dict[name]["vendor"]

        manufacturers_id = vendor
        if vendor:
            manufacturers_id = check_and_post(
                session, urls.MANUFACTURER_URL, {"name": vendor}
            )
        nic_id = check_and_post(
            session,
            urls.DEVICE_NETWORK_CARD_URL,
            {
                "designation": name,
                "bandwidth": bandwidth,
                "manufacturers_id": manufacturers_id,
                "devicenetworkcardmodels_id": nic_model_id,
            },
        )
        nic_item_id = check_and_post(
            session,
            urls.DEVICE_NETWORK_CARD_ITEM_URL,
            {
                "items_id": COMPUTER_ID,
                "itemtype": "Computer",
                "devicenetworkcards_id": nic_id,
                "mac": nics_dict[name]["serial"],
            },
        )
        nic_ids[name] = nic_item_id

    # Create network ports by logical number based off the networks dictionary
    # queried from the machine.
    global switch_dict
    switch_dict = {}
    logical_number = 0
    for name in networks_dict:
        print(name)
        network_port_id = check_and_post_network_port(
            session,
            urls.NETWORK_PORT_URL,
            COMPUTER_ID,
            "Computer",
            logical_number,
            name,
            "NetworkPortEthernet",
            networks_dict[name],
            switch_dict,
            urls,
            switch_info,
        )

        child.sendline("sudo ethtool " + name)
        child.expect(".*\$ ", timeout=30)  # noqa: W605
        network_speed = child.after.strip().decode()
        network_speed_dict = format_dicts.strip_decoded_dict(network_speed, ":")

        speed = ""
        if "Speed" in network_speed_dict and network_speed_dict["Speed"][-4:] == "Mb/s":
            speed = network_speed_dict["Speed"][0:-4]

        nic_id = ""
        if name in nic_ids:
            nic_id = nic_ids[name]

        check_and_post(
            session,
            urls.NETWORK_PORT_ETHERNET_URL,
            {
                "networkports_id": network_port_id,
                "items_devicenetworkcards_id": nic_id,
                "speed": speed,
            },
        )
        logical_number += 1

    # Create Memory types.
    if "MemTotal:" in ram_dict:
        memory_type_id = check_and_post(
            session, urls.DEVICE_MEMORY_TYPE_URL, {"name": "Unspecified"}
        )
        manufacturers_id = check_and_post(
            session, urls.MANUFACTURER_URL, {"name": "Unspecified"}
        )
        memory_id = check_and_post(
            session,
            urls.DEVICE_MEMORY_URL,
            {
                "designation": "Unspecified",
                "frequence": "Unspecified",
                "manufacturers_id": manufacturers_id,
                "size_default": ram_dict["MemTotal:"],
                "devicememorytypes_id": memory_type_id,
            },
        )

        # Create Memory Items.
        check_and_post_device_memory_item(
            session,
            urls.DEVICE_MEMORY_ITEM_URL,
            COMPUTER_ID,
            "Computer",
            memory_id,
            ram_dict["MemTotal:"],
            1,
        )

    # Remove Memory items of 'Unspecified' type, which would have been
    # populated using the Redfish creation script.
    # unspecified_memory_id = get_unspecified_device_memory(
    #    session, DEVICE_MEMORY_URL, 'Unspecified')
    # check_and_remove_unspecified_device_memory_item(
    #    session, DEVICE_MEMORY_ITEM_URL, unspecified_memory_id)

    # Create Disk items.
    for disk_id in disk_dict:
        size = 0
        if disk_dict[disk_id]["Size"][-1:] == "G":
            size = float(disk_dict[disk_id]["Size"][:-1]) * 1000
        elif disk_dict[disk_id]["Size"][-1:] == "T":
            size = float(disk_dict[disk_id]["Size"][:-1]) * 1000000
        else:
            size = float(disk_dict[disk_id]["Size"][:-1])

        check_and_post(
            session,
            urls.DISK_ITEM_URL,
            {
                "items_id": COMPUTER_ID,
                "itemtype": "Computer",
                "name": disk_id,
                "totalsize": size,
            },
        )

    return


# Executes main if run as a script.
if __name__ == "__main__":
    main()
