#!/usr/bin/env python3
"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: create_glpi_computer_redfish.py                                 |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: GLPI REST API Computer upload/update implementation             |
|              modified for gathering server information using the Redfish     |
|              REST API. The intention is to have a more generic, os-agnostic  |
|              approach to gathering server information.                       |
|                                                                              |
|------------------------------------------------------------------------------|
"""
# Imports.
import sys
import socket

sys.path.append("..")
import json
import re
from common.sessionhandler import SessionHandler
from common.urlinitialization import UrlInitialization, validate_url
from common.utils import (
    print_final_help,
    check_and_post,
    check_and_post_device_memory_item,
    check_fields,
    check_field,
)
from common.switches import Switches
from common.parser import argparser
import redfish
import requests
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
        "-l",
        "--lab",
        action="store",
        required=True,
        help="the lab in which this server resides",
    )
    parser.parser.add_argument(
        "--ipmi_ip",
        metavar="ipmi_ip",
        type=str,
        required=True,
        help="the IPMI IP address of the server",
    )
    parser.parser.add_argument(
        "--ipmi_user",
        metavar="ipmi_user",
        type=str,
        required=True,
        help="the IPMI username",
    )
    parser.parser.add_argument(
        "--ipmi_pass",
        metavar="ipmi_pass",
        type=str,
        required=True,
        help="the IPMI password",
    )
    parser.parser.add_argument(
        "--public_ip",
        metavar="public_ip",
        type=str,
        required=True,
        help="the public IP address of the server",
    )
    parser.parser.add_argument(
        "-n",
        "--no_dns",
        metavar="no_dns",
        type=str,
        help="Use this flag if you want to use a custom string as the"
        + "name of this machine instead of using DNS",
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
        metavar="general_config",
        help="path to sunbird config YAML file, see "
        + "integration/sunbird/example_sunbird.yml as an example",
    )
    args = parser.parser.parse_args()

    # Process General Config
    with open(args.general_config, "r") as config_path:
        config_map = yaml.safe_load(config_path)

    if "ACCELERATOR_IDS" in config_map:
        global ACCELERATOR_IDS
        ACCELERATOR_IDS = config_map["ACCELERATOR_IDS"]

    # Process Sunbird Config
    if args.sunbird_config:
        with open(args.sunbird_config, "r") as sunbird_config_path:
            sunbird_config = yaml.safe_load(sunbird_config_path)
    else:
        sunbird_config = args.sunbird_config

    global LAB_CHOICE
    LAB_CHOICE = args.lab

    user_token = args.token
    ip = args.ip
    ipmi_ip = args.ipmi_ip
    ipmi_username = args.ipmi_user
    ipmi_password = args.ipmi_pass
    public_ip = args.public_ip
    no_dns = args.no_dns
    sku = args.sku
    switch_config = args.switch_config
    no_verify = args.no_verify
    sunbird_username = args.sunbird_username
    sunbird_password = args.sunbird_password
    if args.sunbird_url:
        sunbird_url = validate_url(args.sunbird_url)
    else:
        sunbird_url = None
    global TEST
    TEST = args.experiment
    global PUT
    PUT = args.put
    overwrite = args.overwrite

    urls = UrlInitialization(ip)
    Switches(switch_config)

    global REDFISH_BASE_URL
    REDFISH_BASE_URL = "https://" + ipmi_ip

    with redfish.redfish_client(
        base_url=REDFISH_BASE_URL,
        username=ipmi_username,
        password=ipmi_password,
        default_prefix="/redfish/v1",
        timeout=20,
    ) as REDFISH_OBJ:
        update_redfish_system_uri(REDFISH_OBJ, urls)

        system_json = get_redfish_system(REDFISH_OBJ)
        cpu_list = get_processor(REDFISH_OBJ)
        ram_list = get_memory(REDFISH_OBJ)
        storage_list = get_storage(REDFISH_OBJ)
        nic_list, port_list = get_network(REDFISH_OBJ)

    if no_dns:
        hostname = no_dns
    else:
        hostname = get_hostname(public_ip, sku, system_json)

    with SessionHandler(user_token, urls, no_verify) as session:
        post_to_glpi(
            session,
            system_json,
            cpu_list,
            hostname,
            ram_list,
            storage_list,
            nic_list,
            port_list,
            sku,
            urls,
            overwrite,
            sunbird_username,
            sunbird_password,
            sunbird_url,
            sunbird_config,
        )

    print_final_help()


def update_redfish_system_uri(
    redfish_session: redfish.rest.v1.HttpClient, urls: UrlInitialization
) -> None:
    """Update the Redfish URL's to use the name of the system

    Args:
        redfish_session (Redfish HTTP Client): The Redfish client object
        urls (common.urlinitialization.UrlInitialization): GLPI API URL's

    """
    print("Getting Redfish system URI:")
    system_summary = redfish_session.get(urls.REDFISH_SYSTEM_GENERIC)

    if system_summary.status != 200:
        return None
    else:
        system_json = system_summary.dict
        global REDFISH_SYSTEM_URI
        REDFISH_SYSTEM_URI = system_json["Members"][0]["@odata.id"]
        global REDFISH_PROCESSOR_URI
        REDFISH_PROCESSOR_URI = REDFISH_SYSTEM_URI + "/Processors"
        global REDFISH_SIMPLE_STORAGE_URI
        REDFISH_SIMPLE_STORAGE_URI = REDFISH_SYSTEM_URI + "/SimpleStorage"  # May 503
        global REDFISH_SYSTEMS_ETHERNET_INTERFACES_URI
        REDFISH_SYSTEMS_ETHERNET_INTERFACES_URI = (
            REDFISH_SYSTEM_URI + "/EthernetInterfaces"
        )  # May 503 (Needs TAS per manual)
        global REDFISH_MEMORY_URI
        REDFISH_MEMORY_URI = REDFISH_SYSTEM_URI + "/Memory"
        global REDFISH_STORAGE_URI
        REDFISH_STORAGE_URI = REDFISH_SYSTEM_URI + "/Storage"
        global REDFISH_NETWORK_URI
        REDFISH_NETWORK_URI = REDFISH_SYSTEM_URI + "/NetworkInterfaces"


def get_redfish_system(redfish_session: redfish.rest.v1.HttpClient) -> dict:
    """Get the basic information of the system from Redfish

    Args:
        redfish_session (Redfish HTTP Client): The Redfish client object

    Returns:
        dict: the basic information of the system
    """
    print("Getting Redfish system information:")
    system_summary = redfish_session.get(REDFISH_SYSTEM_URI)

    if system_summary.status != 200:
        return {}
    else:
        return system_summary.dict


def get_processor(redfish_session: redfish.rest.v1.HttpClient) -> list:
    """Get information about processors from Redfish

    Args:
        redfish_session (Redfish HTTP Client): The Redfish client object

    Returns:
        cpu_list: Information about processors
    """
    print("Getting Redfish processor information:")
    processor_response = redfish_session.get(REDFISH_PROCESSOR_URI)
    cpu_list = []
    if processor_response.status == 200:
        processor_summary = processor_response.dict
        for cpu in processor_summary.get("Members", []):
            cpu_info = redfish_session.get(cpu["@odata.id"])
            cpu_list.append(cpu_info.text)
    return cpu_list


def get_memory(redfish_session: redfish.rest.v1.HttpClient) -> list:
    """Get RAM information from Redfish

    Args:
        redfish_session (Redfish HTTP Client): The Redfish client object

    Returns:
        ram_list: Information about RAM
    """
    print("Getting Redfish memory information:")
    memory_response = redfish_session.get(REDFISH_MEMORY_URI)
    ram_list = []
    if memory_response.status != 200:
        memory_summary = memory_response.dict
        for ram in memory_summary.get("Members", []):
            ram_info = redfish_session.get(ram["@odata.id"])
            ram_list.append(ram_info.dict)
    return ram_list


def get_storage(redfish_session: redfish.rest.v1.HttpClient) -> list:  # noqa: C901
    """Get drive information from Redfish

    Args:
        redfish_session (Redfish HTTP Client): The Redfish client object

    Returns:
        drive_list (list): Information about drives
    """
    print("Getting Redfish storage information:")
    storage_summary = redfish_session.get(REDFISH_STORAGE_URI)

    drive_list = []
    if (
        "Members" in storage_summary.text
        and json.loads(storage_summary.text)["Members"] != []
        and storage_summary.status == 200
    ):
        for storage in json.loads(storage_summary.text)["Members"]:
            storage_info = redfish_session.get(storage["@odata.id"])
            if (
                "Drives" in storage_info.text
                and json.loads(storage_info.text)["Drives"] != []
            ):
                for drive in json.loads(storage_info.text)["Drives"]:
                    drive_info = redfish_session.get(drive["@odata.id"])
                    drive_list.append(drive_info.text)

    # Get HP-specific disks
    system_summary = get_redfish_system(redfish_session)
    if "Oem" in system_summary:
        if "Hp" in system_summary["Oem"] or "Hpe" in system_summary["Oem"]:
            smart_storage_info = None
            if "Hp" in system_summary["Oem"]:
                if "Links" in system_summary["Oem"]["Hp"]:
                    if "SmartStorage" in system_summary["Oem"]["Hp"]["Links"]:
                        smart_storage_info = redfish_session.get(
                            system_summary["Oem"]["Hp"]["Links"]["SmartStorage"][
                                "@odata.id"
                            ]
                        )
            if "Hpe" in system_summary["Oem"]:
                if "Links" in system_summary["Oem"]["Hpe"]:
                    if "SmartStorage" in system_summary["Oem"]["Hpe"]["Links"]:
                        smart_storage_info = redfish_session.get(
                            system_summary["Oem"]["Hpe"]["Links"]["SmartStorage"][
                                "@odata.id"
                            ]
                        )
            if smart_storage_info:
                if "Links" in smart_storage_info.dict:
                    if "ArrayControllers" in smart_storage_info.dict["Links"]:
                        ac_info = redfish_session.get(
                            smart_storage_info.dict["Links"]["ArrayControllers"][
                                "@odata.id"
                            ]
                        )
                        if "Members" in ac_info.dict:
                            for ac in ac_info.dict["Members"]:
                                ac_member_info = redfish_session.get(ac["@odata.id"])
                                if "Links" in ac_member_info.dict:
                                    if "PhysicalDrives" in ac_member_info.dict["Links"]:
                                        hp_drive_endpoint = redfish_session.get(
                                            ac_member_info.dict["Links"][
                                                "PhysicalDrives"
                                            ]["@odata.id"]
                                        )
                                        if "Members" in hp_drive_endpoint.dict:
                                            for hp_drive in hp_drive_endpoint.dict[
                                                "Members"
                                            ]:
                                                hp_drive_info = redfish_session.get(
                                                    hp_drive["@odata.id"]
                                                )
                                                drive_list.append(hp_drive_info.text)
    return drive_list


def get_network(redfish_session: redfish.rest.v1.HttpClient) -> list:
    """Get nic and network port information from Redfish

    Args:
        redfish_session (Redfish HTTP Client): The Redfish client object

    Returns:
        nic_list, port_list (tuple): Information about network cards and ports
    """
    print("Getting Redfish network information:")
    network_summary = redfish_session.get(REDFISH_NETWORK_URI)
    nic_list = []
    port_list = []
    eth_list = []
    if "Members" in network_summary.text and network_summary.status == 200:
        for nic in json.loads(network_summary.text)["Members"]:
            network_interface = redfish_session.get(nic["@odata.id"])
            if (
                "Links" in network_interface.text
                and "NetworkAdapter" in network_interface.dict["Links"]
            ):
                network_adapter_endpoint = network_interface.dict["Links"][
                    "NetworkAdapter"
                ]["@odata.id"]
                nic_info = redfish_session.get(network_adapter_endpoint)
                nic_list.append(nic_info.text)
                if "NetworkPorts" in nic_info.text:
                    if type(json.loads(nic_info.text)["NetworkPorts"]) == list:
                        ports_info = redfish_session.get(
                            json.loads(nic_info.text)["NetworkPorts"][0]["@odata.id"]
                        )
                    else:
                        ports_info = redfish_session.get(
                            json.loads(nic_info.text)["NetworkPorts"]["@odata.id"]
                        )
                    if "Members" in ports_info.text:
                        for port in json.loads(ports_info.text)["Members"]:
                            if "@odata.id" in port:
                                port_info = redfish_session.get(port["@odata.id"])
                                port_list.append(port_info.text)
    ethernet_summary = redfish_session.get(REDFISH_SYSTEMS_ETHERNET_INTERFACES_URI)
    if "Members" in ethernet_summary.text:
        for eth in json.loads(ethernet_summary.text)["Members"]:
            ethernet_interface = redfish_session.get(eth["@odata.id"])
            eth_list.append(ethernet_interface.text)

    if port_list:
        return nic_list, port_list
    else:
        return nic_list, eth_list


def get_hostname(public_ip, sku, system_json):
    try:
        hostname = socket.gethostbyaddr(public_ip)[0]
    except socket.herror:
        if (
            sku
            and "dell" in system_json["Manufacturer"].lower()
            and "SKU" in system_json
        ):
            print("DNS not working, using SKU as name instead")
            hostname = system_json["SKU"]
        else:
            print("DNS not working, using SerialNumber as name instead")
            hostname = system_json["SerialNumber"]
    return hostname


def post_to_glpi(  # noqa: C901
    session: requests.sessions.Session,
    system_json: dict,
    cpu_list: list,
    hostname: str,
    ram_list: list,
    drive_list: list,
    nics_dict: list,
    networks_dict: list,
    sku: bool,
    urls: UrlInitialization,
    overwrite: bool,
    sunbird_username: str,
    sunbird_password: str,
    sunbird_url: str,
    sunbird_config: dict,
) -> None:
    """A method to post the JSON created to GLPI. This method calls numerous helper
       functions which create different parts of the JSON required, get fields from
       GLPI, and post new fields to GLPI when required. This method takes the GLPIREST
       session and returns when complete.

    Args:
        session (Session object): The requests session object
        system_json (dict): Basic information about the system
        cpu_list (list): Information about processors in system
        hostname (str): Hostname of system
        ram_list (list): Information about RAM in system
        drive_list (list): Information about drives in system
        nics_dict (list): Information about network cards in system
        networks_dict (list): Information about network ports in system
        sku (bool): Determines if SKU should be used instead of Serial Number
        urls (common.urlinitialization.UrlInitialization): GLPI API URL's
        overwrite (bool): flagged to overwrite existing names
        sunbird_username (str): Sunbird username
        sunbird_password (str): Sunbird password
        sunbird_url (str): Sunbird URL
        sunbird_config (dict): a user-provided dictionary of lab locations and cabinets
    """
    if sku and "dell" in system_json["Manufacturer"].lower() and "SKU" in system_json:
        serial_number = system_json["SKU"]
    else:
        serial_number = system_json["SerialNumber"]
    # Append TEST to the serial number if the TEST flag is set.
    if TEST:
        serial_number = serial_number + "_TEST"
    uuid = system_json["UUID"]

    # Call helper functions to check fields present in GLPI for the various
    # machine fields to be populated and post them to GLPI if necessary.
    #
    # NOTE: Different helper functions exist because of different syntax,
    #       field names, and formatting in the API.
    computer_type_id = check_and_post(
        session, urls.COMPUTER_TYPE_URL, {"name": "Server"}
    )

    manufacturers_id = check_and_post(
        session, urls.MANUFACTURER_URL, {"name": system_json["Manufacturer"]}
    )
    computer_model_id = check_and_post(
        session, urls.COMPUTER_MODEL_URL, {"name": system_json["Model"]}
    )
    processors_id = check_and_post_processor(session, cpu_list, urls.CPU_URL, urls)
    locations_id = check_and_post(session, urls.LOCATION_URL, {"name": LAB_CHOICE})

    # The final dictionary for the machine JSON to post.
    glpi_post = {}
    # Add the computer name.
    glpi_post["name"] = hostname

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
    # Add the location.
    glpi_post["locations_id"] = locations_id

    # Get the list of computers and check the serial number. If the serial
    # number matches then use a PUT to modify the cooresponding computer by ID.
    glpi_fields_list = check_fields(session, urls.COMPUTER_URL)
    comment = None
    COMPUTER_ID = None
    for glpi_computer in glpi_fields_list:
        if glpi_computer["serial"] == serial_number:
            global PUT
            PUT = True
            COMPUTER_ID = glpi_computer["id"]
            comment = glpi_computer["comment"]
            if glpi_computer["name"] != glpi_post["name"] and not overwrite:
                print("Using pre-existing name for computer...")
                glpi_post["name"] = glpi_computer["name"]
            break

    # Add BMC Address to the Computer if overwriting existing computer,
    # or creating a new one.
    if overwrite or not PUT:
        plugin_response = check_fields(session, urls.BMC_URL)
        glpi_post = update_bmc_address(
            glpi_post, plugin_response, REDFISH_BASE_URL, comment
        )
    else:
        print("Leaving 'BMC Address' field unchanged...")

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

    # Get Rack Location from Sunbird if all relevant flags are provided
    if all(
        parameter is not None
        for parameter in [sunbird_username, sunbird_password, sunbird_url]
    ):
        add_rack_location_from_sunbird(
            session,
            urls,
            serial_number,
            locations_id,
            COMPUTER_ID,
            sunbird_url,
            sunbird_username,
            sunbird_password,
            sunbird_config,
        )
    else:
        print(
            (
                "To get rack locations from Sunbird, you need to provide the "
                "Sunbird URL, username, and password via the -U, -P, and -S flags."
                "Importing without Sunbird info..."
            )
        )

    # NOTE: The 'check_and_post' style helper methods called below (for the
    # processor(s), operating system, switches, memory, and network) come after
    # the PUT/POST of the machine itself because they require the computer's ID.
    check_and_post_processor_item(
        session,
        cpu_list,
        urls.CPU_ITEM_URL,
        COMPUTER_ID,
        processors_id,
        "Computer",
        len(cpu_list),
    )
    # Create network devices.
    nic_ids = {}
    for name in nics_dict:
        bandwidth = ""
        nic_model_id = 0
        if "Model" in name:
            nic_model_id = check_and_post(
                session,
                urls.DEVICE_NETWORK_CARD_MODEL_URL,
                {"name": json.loads(name)["Model"]},
            )

        vendor = 0
        if "Manufacturer" in name:
            if json.loads(name)["Manufacturer"]:
                vendor = json.loads(name)["Manufacturer"]
            else:
                vendor = "None"

        if "Id" in json.loads(name):
            manufacturers_id = vendor
            if vendor:
                manufacturers_id = check_and_post(
                    session, urls.MANUFACTURER_URL, {"name": vendor}
                )
            nic_id = check_and_post(
                session,
                urls.DEVICE_NETWORK_CARD_URL,
                {
                    "designation": json.loads(name)["Id"],
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
                    "mac": "",
                },
            )
            nic_ids[json.loads(name)["Id"]] = nic_item_id

    # Create network ports by logical number based off the networks dictionary
    # queried from the machine.
    global switch_dict
    switch_dict = {}
    logical_number = 0
    for name in networks_dict:
        search_criteria = {
            "items_id": COMPUTER_ID,
            "itemtype": "Computer",
            "logical_number": logical_number,
            "name": json.loads(name)["Id"],
            "instantiation_type": "NetworkPortEthernet",
        }

        if "AssociatedNetworkAddresses" in json.loads(name):
            additional_information = {
                "mac": json.loads(name)["AssociatedNetworkAddresses"][0]
            }
        elif "MACAddress" in json.loads(name):
            additional_information = {"mac": json.loads(name)["MACAddress"]}
        else:
            additional_information = None
        network_port_id = check_and_post(
            session, urls.NETWORK_PORT_URL, search_criteria, additional_information
        )
        try:
            speed = json.loads(name)["SpeedMbps"]
        except KeyError:
            pass
        try:
            speed = json.loads(name)["SupportedLinkCapabilities"][0]["LinkSpeedMbps"]
        except KeyError:
            speed = 0
        nic_id = ""
        if json.loads(name)["Id"] in nic_ids:
            nic_id = nic_ids[json.loads(name)["Id"]]
        else:
            nic_id = 0
        check_and_post(
            session,
            urls.NETWORK_PORT_ETHERNET_URL,
            {
                "networkports_id": network_port_id,
            },
            {
                "items_devicenetworkcards_id": nic_id,
                "speed": speed,
            },
        )
        logical_number += 1

    # Create Memory types.
    memory_item_dict = {}
    for ram in ram_list:
        if ("Status" in ram and ram["Status"]["State"] == "Enabled") or (
            "DIMMStatus" in ram and ram["DIMMStatus"] == "GoodInUse"
        ):
            if "MemoryDeviceType" in ram:
                memory_type_id = check_and_post(
                    session,
                    urls.DEVICE_MEMORY_TYPE_URL,
                    {"name": ram["MemoryDeviceType"]},
                )
            elif "DIMMType" in ram:  # HP field
                memory_type_id = check_and_post(
                    session, urls.DEVICE_MEMORY_TYPE_URL, {"name": ram["DIMMType"]}
                )
            else:
                memory_type_id = check_and_post(
                    session, urls.DEVICE_MEMORY_TYPE_URL, {"name": "Unspecified"}
                )
            manufacturers_id = check_and_post(
                session, urls.MANUFACTURER_URL, {"name": ram["Manufacturer"].strip()}
            )
            if "TotalSystemMemoryGiB" in system_json["MemorySummary"]:
                total_system_memory = (
                    int(system_json["MemorySummary"]["TotalSystemMemoryGiB"]) * 1000
                )
            else:
                total_system_memory = ""
            if "OperatingSpeedMhz" in ram:
                memory_id = check_and_post(
                    session,
                    urls.DEVICE_MEMORY_URL,
                    {
                        "designation": ram["PartNumber"],
                        "frequence": str(ram["OperatingSpeedMhz"]),
                        "manufacturers_id": manufacturers_id,
                        "size_default": total_system_memory,
                        "devicememorytypes_id": memory_type_id,
                    },
                )
            elif "MaximumFrequencyMHz" in ram:  # HP field
                memory_id = check_and_post(
                    session,
                    urls.DEVICE_MEMORY_URL,
                    {
                        "designation": ram["PartNumber"],
                        "frequence": str(ram["MaximumFrequencyMHz"]),
                        "manufacturers_id": manufacturers_id,
                        "size_default": total_system_memory,
                        "devicememorytypes_id": memory_type_id,
                    },
                )
            if memory_id in memory_item_dict:
                memory_item_dict[memory_id]["quantity"] += 1
            else:
                memory_item_dict[memory_id] = {}
                memory_item_dict[memory_id]["quantity"] = 1
                if "CapacityMiB" in ram:
                    memory_item_dict[memory_id]["size"] = ram["CapacityMiB"]
                elif "SizeMB" in ram:  # HP field
                    memory_item_dict[memory_id]["size"] = ram["SizeMB"]
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
    for disk_id in drive_list:
        disk_id = json.loads(disk_id)
        size = 0
        if "CapacityBytes" in disk_id:
            size = round(float(disk_id["CapacityBytes"]) / 1000000)
        elif "CapacityMiB" in disk_id:
            size = disk_id["CapacityMiB"]
        check_and_post(
            session,
            urls.DISK_ITEM_URL,
            {
                "items_id": COMPUTER_ID,
                "itemtype": "Computer",
                "name": disk_id.get("SerialNumber"),
                "totalsize": size,
            },
        )

    return


def update_bmc_address(
    glpi_post: dict,
    plugin_response: list,
    redfish_base_url: str,
    comment: str,
) -> dict:
    """Add BMC address to glpi_post

    Args:
        glpi_post (dict): Contains information about a Computer to be passed to GLPI
        plugin_response (list): list of requests objects returned by BMC API endpoint
        redfish_base_url (str): URL used to connect to Redfish
        comment (str): Comment of computer in GLPI. None if this field is empty

    Returns:
        glpi_post (dict): Contains information about a Computer to be passed to GLPI
    """
    if "ERROR" in plugin_response[0]:
        glpi_post = add_bmc_address_to_comments(glpi_post, redfish_base_url, comment)
        print(
            "The provided field endpoint is unavailable, "
            + "adding the BMC address to the comments."
        )
    else:
        print("Setting the 'BMC Address' field...")
        glpi_post = set_bmc_address_field(glpi_post, redfish_base_url)

    return glpi_post


def add_bmc_address_to_comments(
    glpi_post: dict, redfish_base_url: str, comment: str
) -> dict:
    """Add BMC address to comments of GLPI post.

    Args:
        glpi_post (dict): Contains information about a Computer to be passed to GLPI
        redfish_base_url (str): URL used to connect to Redfish
        comment (str): Comment of computer in GLPI. None if this field is empty

    Returns:
        glpi_post (str): Contains information about a Computer to be passed to GLPI
    """
    if comment:
        if "BMC Address" not in comment:
            glpi_post["comment"] = (
                comment + "\nBMC Address: " + redfish_base_url.partition("https://")[2]
            )
        else:
            # replace IP address within comment body
            pattern = r"BMC Address: (\d+\.\d+\.\d+\.\d+)"
            replacement = f'BMC Address: {redfish_base_url.partition("https://")[2]}'
            updated_text = re.sub(pattern, replacement, comment)
            glpi_post["comment"] = updated_text
    else:
        glpi_post["comment"] = (
            "BMC Address: " + redfish_base_url.partition("https://")[2]
        )

    return glpi_post


def set_bmc_address_field(
    glpi_post: dict,
    redfish_base_url: str,
) -> dict:
    """Set BMC address field of GLPI post
    Args:
        glpi_post (dict): Contains information about a Computer to be passed to GLPI
        redfish_base_url (str): URL used to connect to Redfish

    Returns:
        glpi_post (dict): Contains information about a Computer to be passed to GLPI
    """
    glpi_post["bmcaddressfield"] = redfish_base_url.partition("https://")[2]
    print("Updating BMC Address Field...")
    return glpi_post


def add_rack_location_from_sunbird(
    session: requests.sessions.Session,
    urls: UrlInitialization,
    serial_number: str,
    locations_id: int,
    computer_id: int,
    sunbird_url: str,
    sunbird_username: str,
    sunbird_password: str,
    sunbird_config: dict,
) -> None:
    """A method to check for a computer's rack location in Sunbird and post it to GLPI.
    If not all three of sunbird_username, sunbird_password, and sunbird_config are set,
    the check will be skipped and the import will continue without Sunbird data.

    Args:
        session (Session object): The requests session object
        urls (common.urlinitialization.UrlInitialization): GLPI API URL's
        serial_number (str): Serial number of the relevant computer
        locations_id (int): ID of the geographic location of the relevant computer
        computer_id (int): ID of the relevant computer
        sunbird_username (str): Sunbird username
        sunbird_password (str): Sunbird password
        sunbird_url (str): Sunbird URL
        sunbird_config (dict): A user-provided dictionary of lab locations and cabinets
    """
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "columns": [{"name": "tiSerialNumber", "filter": {"eq": serial_number}}],
        "selectedColumns": [
            {"name": "cmbLocation"},
            {"name": "cmbCabinet"},
            {"name": "cmbUPosition"},
            {"name": "tiDataCenterName"},
            {"name": "tiRoomName"},
            {"name": "tiRUs"},
        ],
        "customFieldByLabel": True,
    }
    sunbird_response = requests.post(
        f"{sunbird_url}/api/v2/quicksearch/items",
        headers=headers,
        json=payload,
        verify=False,
        auth=(sunbird_username, sunbird_password),
    )
    sunbird_json = sunbird_response.json()["searchResults"]["items"]
    if sunbird_json:
        sunbird_location_data = sunbird_json[0]
        if sunbird_location_data["cmbLocation"] in sunbird_config:
            location_config = sunbird_config[sunbird_location_data["cmbLocation"]]

        else:
            location_config = None

        # If not explicitly provided, set the data center and room to any text before
        # the first > and after the last >. So Example > 01 > Test becomes
        # (Example, Test). Do this if the location of the machine in Sunbird isn't
        # found in the provided config file.
        if location_config is None or (
            "Data Center" not in location_config and "Room" not in location_config
        ):
            print(
                "No Sunbird config provided, setting data center and room automatically"
            )
            data_center = sunbird_location_data.get("tiDataCenterName", None)
            if "tiRoomName" in sunbird_location_data:
                room = sunbird_location_data["tiRoomName"]
            # If the Room is not specified in Sunbird, use the Data Center name
            elif data_center is not None:
                room = sunbird_location_data["tiDataCenterName"]
            else:
                room = None
        else:
            data_center = location_config.get("Data Center", None)
            room = location_config.get("Room", None)
            if room is None:
                if data_center is not None:
                    room = sunbird_location_data["tiDataCenterName"]

        location_details = {
            "location": locations_id,
            "full_location": sunbird_location_data["cmbLocation"],
            "DataCenter": data_center,
            "Room": room,
        }

        location_details["Rack"] = sunbird_location_data.get("cmbCabinet", None)

        if sunbird_location_data["cmbUPosition"]:
            location_details["Item_Rack"] = int(sunbird_location_data["cmbUPosition"])
        else:
            location_details["Item_Rack"] = None

        # Get size of asset, otherwise default to 1 RU
        if "tiRUs" in sunbird_location_data:
            location_details["required_units"] = int(sunbird_location_data["tiRUs"])
        else:
            location_details["required_units"] = 1
        # Check for Data Center
        if location_details["DataCenter"] is None:
            print("No Data Center could be retrieved from Sunbird, moving on...")
            return

        dc_id = check_and_post(
            session,
            urls.DATACENTER_URL,
            {
                "locations_id": location_details["location"],
                "name": location_details["DataCenter"],
            },
        )

        # Check for Data Center Room
        if location_details["Room"] is None:
            print("No Data Center Room was retrieved from Sunbird, moving on...")
            return

        dcrooms_id = check_and_post(
            session,
            urls.DCROOM_URL,
            {
                "locations_id": location_details["location"],
                "name": str(location_details["Room"]),
                "datacenters_id": dc_id,
            },
        )

        # Check for Rack
        if location_details["Rack"] is None:
            print("No cabinet could be retrieved from Sunbird, moving on...")
            return

        number_units = get_rack_units(
            location_details, sunbird_url, sunbird_username, sunbird_password
        )
        rack_id = check_and_post(
            session,
            urls.RACK_URL,
            {"name": location_details["Rack"], "dcrooms_id": dcrooms_id},
            {
                "number_units": number_units,
                "bgcolor": "#fec95c",  # Hardcoded, otherwise the rack won't show in UI
            },
        )

        # Check for Item Rack
        if location_details["Item_Rack"] is None:
            print(
                (
                    "No U Position was retrieved from Sunbird, "
                    "computer will not be assigned to rack."
                )
            )
            return

        check_and_update_model_size(
            session, field=location_details, urls=urls, computer_id=computer_id
        )

        check_and_post(
            session,
            urls.ITEM_RACK_URL,
            {
                "itemtype": "Computer",
                "items_id": computer_id,
            },
            {
                "position": location_details["Item_Rack"],
                "racks_id": rack_id,
                "bgcolor": "#69ceba",  # Hardcoded, otherwise the rack won't show in UI
                "orientation": 0,  # Hardcoded, otherwise the rack won't show in UI
            },
        )
        print(
            (
                f"Added computer to {location_details['DataCenter']} > "
                f"{location_details['Room']} > {location_details['Rack']} > "
                f"{location_details['Item_Rack']}"
            )
        )

    else:
        print("Couldn't find machine in Sunbird, moving on without location details")


def get_rack_units(
    field: dict, sunbird_url: str, sunbird_username: str, sunbird_password: str
) -> int:
    """Retrieve the number of units in the rack from Sunbird

    Args:
        field (dict): Contains information about the rack location
        sunbird_username (str): Sunbird username
        sunbird_password (str): Sunbird password
        sunbird_url (str): Sunbird URL

    Returns:
        int: Number of units in rack
    """
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "columns": [
            {"name": "tiClass", "filter": {"eq": "Cabinet"}},
            {"name": "cmbLocation", "filter": {"eq": field["full_location"]}},
            {"name": "cmbCabinet", "filter": {"eq": field["Rack"]}},
        ],
        "selectedColumns": [{"name": "tiRUs"}],
        "customFieldByLabel": True,
    }
    sunbird_response = requests.post(
        f"{sunbird_url}/api/v2/quicksearch/items",
        headers=headers,
        json=payload,
        verify=False,
        auth=(sunbird_username, sunbird_password),
    )
    sunbird_json = sunbird_response.json()["searchResults"]["items"][0]

    number_units = int(sunbird_json["tiRUs"])

    return number_units


def check_and_update_model_size(
    session: requests.sessions.Session,
    field: dict,
    urls: UrlInitialization,
    computer_id: int,
) -> None:
    """Update a computer model's size if it doesn't match information from Sunbird

    Args:
        Session (Session object): The requests session object
        field (dict): Contains information about the rack location
        urls (common.urlinitialization.UrlInitialization): GLPI API URL's
        computer_id (int): ID of the computer associated with the rack item
    """
    computer_info = session.get(url=urls.COMPUTER_URL + f"/{computer_id}")
    computer_model_id = computer_info.json()["computermodels_id"]
    computer_model_info = session.get(
        url=urls.COMPUTER_MODEL_URL + f"/{computer_model_id}"
    )
    required_units = computer_model_info.json()["required_units"]
    if required_units != field["required_units"]:
        print(
            f"Modifying model size from {required_units} to {field['required_units']}"
        )
        glpi_put = {"required_units": field["required_units"], "id": computer_model_id}
        session.put(url=urls.COMPUTER_MODEL_URL, json={"input": glpi_put})


def check_and_post_processor(
    session: requests.sessions.Session, field: list, url: str, urls: UrlInitialization
) -> int:
    """A helper method to check the processor field at the given API endpoint (URL)
       and post the field if it is not present.

       NOTE: The CPU API has differing fields (designation instead of name, extra
       fields to populate, and misspelled fields["frequence" should clearly be
       "frequency"]).

    Args:
        session (Session object): The requests session object
        field (list): Contains information about processors
        url (str): GLPI API endpoint for processors
        urls (common.urlinitialization.UrlInitialization): GLPI API URL's

    Returns:
        id (int): GLPI ID of system processor
    """
    field = json.loads(field[0])
    if field["ProcessorType"] == "CPU":
        print("Checking GLPI CPU fields:")
        # Check if the field is present at the URL endpoint.
        if field["Model"]:
            search_criteria = field["Model"]
        else:
            search_criteria = field["ProcessorId"]["VendorId"]
        id = check_field(session, url, search_criteria={"designation": search_criteria})

        # Create a field if one was not found and return the ID.
        if id is None:
            # Get the manufacturer or create it (NOTE: This may create duplicates
            # with slight variation)
            manufacturers_id = check_and_post(
                session, urls.MANUFACTURER_URL, {"name": field["Manufacturer"]}
            )
            print("Creating GLPI CPU field:")
            glpi_post = {
                "designation": search_criteria,
                "nbcores_default": field["TotalCores"],
                "nbthreads_default": field["TotalThreads"],
                "manufacturers_id": manufacturers_id,
            }
            post_response = session.post(url=url, json={"input": glpi_post})
            print(str(post_response) + "\n")
            id = post_response.json()["id"]

        return id


def check_and_post_processor_item(
    session: requests.sessions.Session,
    field: list,
    url: str,
    item_id: int,
    processor_id: int,
    item_type: str,
    sockets: int,
) -> None:
    """A helper method to check the processor item field at the given API endpoint
    (URL) and post the field if it is not present.

    NOTE: The CPU Item API differs from the regular Processor component API. This
    is where it is associated with the "item" (the computer). The field names also
    differ from the normal processor API, even if they are repeated.

    Args:
        session (Session object): The requests session object
        field (list): Contains information about processors
        url (str): GLPI API endpoint for processors
        item_id (int): ID of the computer that the processor is associated with
        processor_id (int): ID of the processor itself
        item_type (str): Type of item associated with processor, usually "Computer"
        sockets (int): Number of processors associated with the computer
    """
    field = json.loads(field[0])
    if field["ProcessorType"] == "CPU":
        # Check if the field is present at the URL endpoint.
        print("Checking GLPI Processor fields:")
        ids = []
        glpi_fields_list = check_fields(session, url)

        for glpi_field in glpi_fields_list:
            if (
                glpi_field["items_id"] == item_id
                and glpi_field["itemtype"] == item_type
                and glpi_field["deviceprocessors_id"] == processor_id
            ):
                ids.append(glpi_field["id"])
                if len(ids) == sockets:
                    break

        print("Creating GLPI CPU Item field:")
        glpi_post = {
            "items_id": item_id,
            "itemtype": item_type,
            "deviceprocessors_id": processor_id,
            "nbcores": field["TotalCores"],
            "nbthreads": field["TotalThreads"],
        }
        for id in ids:
            post_response = session.put(url=url, json={"input": glpi_post})
            print(str(post_response) + "\n")
        for i in range(sockets - len(ids)):
            post_response = session.post(url=url, json={"input": glpi_post})
            print(str(post_response) + "\n")

        return


# Executes main if run as a script.
if __name__ == "__main__":
    main()
