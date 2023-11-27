#!/usr/bin/env python3
"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: create_glpi_computer.py                                         |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: GLPI REST API Computer upload/update implementation.            |
|                                                                              |
|------------------------------------------------------------------------------|
"""
# Local modules.
import sys

sys.path.append("..")
import common.format_dicts as format_dicts

# Imports.
import requests
import subprocess
from common.utils import (
    print_final_help,
    check_and_post,
    check_and_post_processor,
    check_and_post_processor_item,
    check_and_post_operating_system_item,
    check_and_post_device_memory,
    check_and_post_device_memory_item,
    check_and_post_disk_item,
    check_and_post_network_port,
    check_and_post_network_port_ethernet,
    check_and_post_nic,
    check_and_post_nic_item,
    check_fields,
    create_or_update_glpi_item,
    check_field,
)
from common.sessionhandler import SessionHandler
from common.urlinitialization import UrlInitialization
from common.switches import Switches
from common.parser import argparser

# Suppress InsecureRequestWarning caused by REST access to Redfish without
# certificate validation.
import urllib3
import yaml

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
        "-id",
        "--computer_id",
        metavar="computer_id",
        type=str,
        required=False,
        default="",
        help="the id of the computer",
    )
    parser.parser.add_argument(
        "-o",
        "--overwrite",
        action="store_true",
        help="Use this flag if you want to overwrite existing names",
    )
    args = parser.parser.parse_args()

    with open(args.general_config, "r") as config_path:
        config_map = yaml.safe_load(config_path)

    if "ACCELERATOR_IDS" in config_map:
        global ACCELERATOR_IDS
        ACCELERATOR_IDS = config_map["ACCELERATOR_IDS"]

    ip = args.ip
    user_token = args.token
    no_verify = args.no_verify
    switch_config = args.switch_config
    global TEST
    TEST = args.experiment
    global PUT
    PUT = args.put
    global COMPUTER_ID
    COMPUTER_ID = args.computer_id
    overwrite = args.overwrite

    urls = UrlInitialization(ip)
    switch_info = Switches(switch_config)
    with SessionHandler(user_token, urls, no_verify) as session:
        post_to_glpi(session, urls, switch_info, overwrite)

    print_final_help()


def post_to_glpi(  # noqa: C901
    session: requests.sessions.Session,
    urls: UrlInitialization,
    switch_info: Switches,
    overwrite: bool,
) -> None:
    """A method to post the JSON created to GLPI. This method calls numerous helper
       functions which create different parts of the JSON required, get fields from
       GLPI, and post new fields to GLPI when required.

    Args:
        session (Session object): The requests session object
        urls (UrlInitialization object): the URL object
        switch_info (Switches object): Contains information about lab switches
        overwrite (boolean): flagged to overwrite existing names
    """
    print("Getting local machine information\n")
    # Get the hostnamectl output as an example, splitting on newlines.
    hostnamectl_output = subprocess.check_output(["hostnamectl"]).splitlines()
    # Get the serial number of the machine.
    serial_number = (
        subprocess.check_output(["dmidecode", "-s", "system-serial-number"])
        .strip()
        .decode()
    )
    # Append TEST to the serial number if the TEST flag is set.
    if TEST:
        serial_number = serial_number + "_TEST"
    # Get the manufacturer of the machine.
    computer_type = (
        subprocess.check_output(["dmidecode", "-s", "system-manufacturer"])
        .strip()
        .decode()
    )
    # Get the model of the machine.
    computer_model = (
        subprocess.check_output(["dmidecode", "-s", "system-product-name"])
        .strip()
        .decode()
    )
    # Get the uuid.
    uuid = subprocess.check_output(["dmidecode", "-s", "system-uuid"]).strip().decode()
    # Get the processor(s).
    lscpu_output = subprocess.check_output(["lscpu"]).splitlines()
    # Get the OS.
    os = subprocess.check_output(["cat", "/etc/os-release"]).strip().decode()
    # Get the kernel version.
    kernel = subprocess.check_output(["uname", "-r"]).strip().decode()
    # Get the architecure version.
    architecture = subprocess.check_output(["uname", "-m"]).strip().decode()
    # Get all interfaces.
    networks = subprocess.check_output(["ifconfig"]).strip().decode()
    # Get RAM information.
    ram = subprocess.check_output(["dmidecode", "--type", "memory"]).strip().decode()
    # Get volume information.
    disks = subprocess.check_output(["parted", "-l", "-s"]).strip().decode()
    # Get NIC information.
    nics = subprocess.check_output(["lshw", "-class", "network"]).strip().decode()
    # Get GPU information.
    gpus = subprocess.check_output(["lshw", "-C", "display"]).strip().decode()

    # Get lspci output.
    lspci = subprocess.Popen(["lspci"], stdout=subprocess.PIPE)
    try:
        grep_lspci = subprocess.check_output(
            ["grep", "accelerators"], stdin=lspci.stdout
        )
        lspci.wait()
        accelerators = grep_lspci.strip().decode()
    except subprocess.CalledProcessError:
        accelerators = ""

    # Strip leading whitespace and create dictionaries of the entries.
    hostnamectl_dict = format_dicts.strip_dict(hostnamectl_output, ": ")
    cpu_dict = format_dicts.strip_dict(lscpu_output, ": ")
    os_dict = format_dicts.strip_decoded_dict(os, "=")
    networks_dict = format_dicts.strip_network_dict(networks, ": ")
    ram_dict = format_dicts.strip_ram_dict(ram, ": ")
    disk_dict = format_dicts.strip_disks_dict(disks, ": ")
    nics_dict = format_dicts.strip_nics_dict(nics, "*", ": ")
    gpus_dict = format_dicts.strip_gpu_dict(gpus, "*", ": ")
    accelerator_dict = format_dicts.strip_accelerator_dict(accelerators, " ")

    # Call helper functions to check fields present in GLPI for the various
    # machine fields to be populated and post them to GLPI if necessary.
    #
    # NOTE: Different helper functions exist because of different syntax,
    #       field names, and formatting in the API.
    computer_type_id = check_and_post(
        session, hostnamectl_dict["Chassis"].capitalize(), urls.COMPUTER_TYPE_URL
    )
    manufacturers_id = check_and_post(session, computer_type, urls.MANUFACTURER_URL)
    computer_model_id = check_and_post(session, computer_model, urls.COMPUTER_MODEL_URL)
    processors_id = check_and_post_processor(session, cpu_dict, urls.CPU_URL, urls)
    operating_system_id = check_and_post(
        session, os_dict["NAME"], urls.OPERATING_SYSTEM_URL
    )
    operating_system_version_id = check_and_post(
        session, os_dict["VERSION"], urls.OPERATING_SYSTEM_VERSION_URL
    )
    operating_system_architecture_id = check_and_post(
        session, architecture, urls.OPERATING_SYSTEM_ARCHITECTURE_URL
    )
    operating_system_kernel_version_id = check_and_post(
        session, kernel, urls.OPERATING_SYSTEM_KERNEL_VERSION_URL
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

    operating_system_id = check_and_post_operating_system_item(
        session,
        urls.OPERATING_SYSTEM_ITEM_URL,
        operating_system_id,
        operating_system_version_id,
        operating_system_architecture_id,
        operating_system_kernel_version_id,
        COMPUTER_ID,
        "Computer",
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
                session, nics_dict[name]["product"], urls.DEVICE_NETWORK_CARD_MODEL_URL
            )

        vendor = 0
        if "vendor" in nics_dict[name]:
            vendor = nics_dict[name]["vendor"]

        nic_id = check_and_post_nic(
            session,
            urls.DEVICE_NETWORK_CARD_URL,
            name,
            bandwidth,
            vendor,
            nic_model_id,
            urls,
        )
        nic_item_id = check_and_post_nic_item(
            session,
            urls.DEVICE_NETWORK_CARD_ITEM_URL,
            COMPUTER_ID,
            "Computer",
            nic_id,
            nics_dict[name]["serial"],
        )
        nic_ids[name] = nic_item_id

    # Create graphics devices.
    gpu_ids = {}
    for name in gpus_dict:
        """bandwidth = ''
        if 'capacity' in nics_dict[name]:
            bandwidth = nics_dict[name]['capacity']"""

        gpu_model_id = 0
        if "product" in gpus_dict[name]:
            gpu_model_id = check_and_post(
                session, gpus_dict[name]["product"], urls.DEVICE_GRAPHICS_CARD_MODEL_URL
            )

        vendor = 0
        if "vendor" in gpus_dict[name]:
            vendor = gpus_dict[name]["vendor"]

        gpu_id = check_and_post_gpu(
            session, urls.DEVICE_GRAPHICS_CARD_URL, name, vendor, gpu_model_id, urls
        )
        gpu_item_id = check_and_post_gpu_item(
            session, urls.DEVICE_GRAPHICS_CARD_ITEM_URL, COMPUTER_ID, "Computer", gpu_id
        )
        gpu_ids[name] = gpu_item_id

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
        try:
            network_speed = subprocess.check_output(["ethtool", name]).strip().decode()
            network_speed_dict = format_dicts.strip_decoded_dict(network_speed, ":")
            speed = 0
            if (
                "Speed" in network_speed_dict
                and network_speed_dict["Speed"][-4:] == "Mb/s"
            ):
                speed = network_speed_dict["Speed"][0:-4]
        except subprocess.CalledProcessError:
            speed = 0

        nic_id = 0
        if name in nic_ids:
            nic_id = nic_ids[name]

        check_and_post_network_port_ethernet(
            session, urls.NETWORK_PORT_ETHERNET_URL, network_port_id, speed, nic_id
        )
        logical_number += 1

    # Create Memory types.
    memory_item_dict = {}
    for memory in ram_dict:
        if (
            "Type" in ram_dict[memory]
            and ram_dict[memory]["Size"] != "No Module Installed"
        ):
            if ram_dict[memory]["Size"].split()[1] == "GB":
                ram_size = int(ram_dict[memory]["Size"].split()[0]) * 1000
            else:
                ram_size = int(ram_dict[memory]["Size"].split()[0])
            memory_type_id = check_and_post(
                session, ram_dict[memory]["Type"], urls.DEVICE_MEMORY_TYPE_URL
            )
            manufacturers_id = check_and_post(
                session, ram_dict[memory]["Manufacturer"], urls.MANUFACTURER_URL
            )
            memory_id = check_and_post_device_memory(
                session,
                urls.DEVICE_MEMORY_URL,
                ram_dict[memory]["Part Number"],
                ram_dict[memory]["Speed"].split()[0],
                manufacturers_id,
                ram_size,
                memory_type_id,
            )
            if memory_id in memory_item_dict:
                memory_item_dict[memory_id]["quantity"] += 1
            else:
                memory_item_dict[memory_id] = {}
                memory_item_dict[memory_id]["quantity"] = 1
                memory_item_dict[memory_id]["size"] = ram_size
    # Create Memory Items.
    for memory_id in memory_item_dict:
        check_and_post_device_memory_item(
            session,
            urls.DEVICE_MEMORY_ITEM_URL,
            COMPUTER_ID,
            "Computer",
            memory_id,
            memory_item_dict[memory_id]["size"],
            memory_item_dict[memory_id]["quantity"],
        )

    # Create Disk items.
    for disk_id in disk_dict:
        size = 0
        if disk_dict[disk_id]["Size"][-2:] == "GB":
            size = float(disk_dict[disk_id]["Size"][:-2]) * 1000
        else:
            size = float(disk_dict[disk_id]["Size"][:-2])

        check_and_post_disk_item(
            session,
            urls.DISK_ITEM_URL,
            COMPUTER_ID,
            "Computer",
            disk_id,
            size,
            disk_dict[disk_id]["Part"],
        )

    for accelerator in accelerator_dict:
        manufacturers_id = check_and_post(
            session,
            accelerator_dict[accelerator]["manufacturer"],
            urls.MANUFACTURER_URL,
        )
        type_id = check_and_post_generic_type(
            session, "Processing accelerators", urls.DEVICE_GENERIC_TYPE_URL
        )
        generic_id = check_and_post_device_generic(
            session,
            urls.DEVICE_GENERIC_URL,
            ACCELERATOR_IDS[accelerator_dict[accelerator]["device"]],
            manufacturers_id,
            type_id,
        )
        check_and_post_device_generic_item(
            session, urls.DEVICE_GENERIC_ITEM_URL, COMPUTER_ID, "Computer", generic_id
        )

    return


def check_and_post_gpu(
    session: requests.sessions.Session,
    url: str,
    name: str,
    vendor: str,
    gpu_model_id: int,
    urls: UrlInitialization,
) -> int:
    """A helper method to check the graphics field at the given API endpoint (URL) and
       post the field if it is not present.

    Args:
        session (Session object): The requests session object
        url (str): GLPI API endpoint of the graphics card device
        name (str): Model name of the GPU
        vendor (str): Manufacturer of the GPU
        gpu_model_id (str): ID of the GPU model in GLPI
        urls (UrlInitialization object): the URL object

    Returns:
        id (int): ID of the GPU in GLPI
    """
    manufacturers_id = vendor
    if vendor:
        manufacturers_id = check_and_post(session, vendor, urls.MANUFACTURER_URL)
    # Check if the field is present at the URL endpoint.
    print("Checking GLPI Graphics fields:")
    id = check_field(
        session,
        url,
        search_criteria={
            "designation": name,
            "manufacturers_id": manufacturers_id,
            "devicegraphiccardmodels_id": gpu_model_id,
        },
    )

    # Create a field if one was not found and return the ID.
    print("Creating GLPI GPU field:")
    glpi_post = {
        "designation": name,
        "manufacturers_id": manufacturers_id,
        "devicegraphiccardmodels_id": gpu_model_id,
    }

    id = create_or_update_glpi_item(session, url, glpi_post, id)

    return id


def check_and_post_gpu_item(
    session: requests.sessions.Session, url: str, item_id: int, item: str, gpu_id: int
) -> int:
    """A helper method to check the graphics item field at the given API endpoint (URL)
       and post the field if it is not present.

    Args:
        session (Session object): requests.sessions.Session
        url (str): GLPI API endpoint for the graphics card item
        item_id (int): ID of the item (usually a computer) associated with the memory
                       item
        item_type (str): Type of the item associated with the memory item, usually
                         "Computer"
        gpu_id (int): ID of the GPU in GLPI
    """
    # Check if the field is present at the URL endpoint.
    print("Checking GLPI GPU Item fields:")
    id = check_field(
        session,
        url,
        search_criteria={
            "items_id": item_id,
            "itemtype": item,
            "devicegraphiccards_id": gpu_id,
        },
    )

    # Create a field if one was not found and return the ID.
    print("Creating GLPI GPU Item field:")
    glpi_post = {"items_id": item_id, "itemtype": item, "devicegraphiccards_id": gpu_id}

    id = create_or_update_glpi_item(session, url, glpi_post, id)

    return id


def check_and_post_generic_type(
    session: requests.sessions.Session, type: str, url: str
) -> int:
    """A helper method to check the generic type field at the given API endpoint (URL)
       and post the field if it is not present.

    Args:
        session (Session object): The requests session object
        type (str): Type of device
        url (str): GLPI API endpoint of the generic type

    Returns:
        id (int): ID of the generic type in GLPI
    """
    # Check if the field is present at the URL endpoint.
    print("Checking GLPI Generic Type fields:")
    id = check_field(session, url, search_criteria={"name": type})

    # Create a field if one was not found and return the ID.
    print("Creating GLPI Generic Type field:")
    glpi_post = {"name": type}

    id = create_or_update_glpi_item(session, url, glpi_post, id)

    return id


def check_and_post_device_generic(
    session: requests.sessions.Session,
    url: str,
    device: str,
    manufacturers_id: int,
    type_id: int,
) -> int:
    """A helper method to check the generic device field at the given API endpoint
       (URL) and post the field if it is not present.

    Args:
        session (Session object): The requests session object
        url (str): GLPI API endpoint of the generic device
        device (str): Name of device
        manufacturers_id (int): ID of manufacturer in GLPI
        type_id (int): ID of device type in GLPI

    Returns:
        id (int): ID of the generic device in GLPI
    """
    # Check if the field is present at the URL endpoint.
    print("Checking GLPI Generic fields:")
    id = check_field(
        session,
        url,
        search_criteria={
            "designation": device,
            "devicegenerictypes_id": type_id,
            "manufacturers_id": manufacturers_id,
        },
    )

    # Create a field if one was not found and return the ID.
    print("Creating GLPI Generic field:")
    glpi_post = {
        "designation": device,
        "devicegenerictypes_id": type_id,
        "manufacturers_id": manufacturers_id,
    }

    id = create_or_update_glpi_item(session, url, glpi_post, id)

    return id


def check_and_post_device_generic_item(
    session: requests.sessions.Session,
    url: str,
    item_id: int,
    item_type: int,
    generic_id: int,
) -> int:
    """A helper method to check the generic device item field at the given API endpoint
       (URL) and post the field if it is not present.

    Args:
        session (Session object): The requests session object
        url (str): GLPI API endpoint of the generic device item
        item_id (int): ID of the item (usually a computer) associated with the disk item
        item_type (str): Type of the item associated with the disk item, usually
                         "Computer"
        generic_id (int): ID of device in GLPI

    Returns:
        id (int): ID of the generic device in GLPI
    """
    # Check if the field is present at the URL endpoint.
    print("Checking GLPI Generic Item fields:")
    id = check_field(
        session,
        url,
        search_criteria={
            "items_id": item_id,
            "itemtype": item_type,
            "devicegenerics_id": generic_id,
        },
    )

    # Create a field if one was not found and return the ID.
    print("Creating GLPI Generic field:")
    glpi_post = {
        "items_id": item_id,
        "itemtype": item_type,
        "devicegenerics_id": generic_id,
    }

    id = create_or_update_glpi_item(session, url, glpi_post, id)

    return id


# Executes main if run as a script.
if __name__ == "__main__":
    main()
