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
import argparse
import traceback

sys.path.append("..")
import re
from common.sessionhandler import SessionHandler
from common.urlinitialization import UrlInitialization, validate_url
from common.utils import (
    print_final_help,
    check_and_post,
    check_and_post_device_memory_item,
    check_fields,
    check_field,
    print_error_table,
    post_accelerators
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
        help="the lab in which this server resides",
    )
    parser.parser.add_argument(
        "--ipmi_ip",
        metavar="ipmi_ip",
        type=str,
        help="the IPMI IP address of the server",
    )
    parser.parser.add_argument(
        "--ipmi_user",
        metavar="ipmi_user",
        type=str,
        help="the IPMI username",
    )
    parser.parser.add_argument(
        "--ipmi_pass",
        metavar="ipmi_pass",
        type=str,
        help="the IPMI password",
    )
    parser.parser.add_argument(
        "--public_ip",
        metavar="public_ip",
        type=str,
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
        help="Use this flag if you want to use the SKU of this machine"
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
    parser.parser.add_argument(
        "--sku_for_dell",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="use the --sku_for_dell if you want to use sku's for dells, and "
        + "serial_numbers for everything else. Use --no-sku_for_dell if you want to "
        + "use serial numbers/sku's for every device, regardless of manufacturer.",
    )
    parser.parser.add_argument(
        "-m",
        "--machine_list",
        metavar="machine_list",
        help="path to file that contains information of multiple machines."
        + "Use this flag if you would like to import multiple machines",
    )
    parser.parser.add_argument(
        "-f",
        "--file_path",
        metavar="file_path",
        help="Path to output file. If omitted, results will not be saved to file",
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

    user_token = args.token
    ip = args.ip
    no_dns = args.no_dns
    sku = args.sku
    sku_for_dell = args.sku_for_dell
    switch_config = args.switch_config
    no_verify = args.no_verify
    sunbird_username = args.sunbird_username
    sunbird_password = args.sunbird_password
    if args.sunbird_url:
        sunbird_url = validate_url(args.sunbird_url)
    else:
        sunbird_url = None
    machines = parse_machine_flags(args)
    global TEST
    TEST = args.experiment
    global PUT
    PUT = args.put
    overwrite = args.overwrite
    file_path = args.file_path

    urls = UrlInitialization(ip)
    Switches(switch_config)
    error_messages = {}
    for machine in machines:
        print(f"Importing {machine['ipmi_ip']}")
        try:
            global REDFISH_BASE_URL
            REDFISH_BASE_URL = "https://" + machine["ipmi_ip"]

            REDFISH_OBJ = redfish.redfish_client(
                base_url=REDFISH_BASE_URL,
                username=machine["ipmi_username"],
                password=machine["ipmi_password"],
                default_prefix="/redfish/v1",
                timeout=20,
            )
            REDFISH_OBJ.login(auth="session")
            update_redfish_system_uri(REDFISH_OBJ, urls)

            system_json = get_redfish_system(REDFISH_OBJ)
            cpu_list = get_processor(REDFISH_OBJ)
            ram_list = get_memory(REDFISH_OBJ)
            storage_list = get_storage(REDFISH_OBJ)
            nic_list, port_list = get_network(REDFISH_OBJ)
            accelerators = get_accelerators(REDFISH_OBJ, system_json, cpu_list)
            try:
                REDFISH_OBJ.logout()
            except redfish.rest.v1.RetriesExhaustedError:
                print("Unable to logout from Redfish, continuing...")
                pass
            except redfish.rest.v1.BadRequestError:
                print("Unable to logout from Redfish, continuing...")
                pass
            if no_dns:
                hostname = no_dns
            else:
                hostname = get_hostname(machine["public_ip"], sku, system_json)

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
                    sku_for_dell,
                    machine["lab_choice"],
                    accelerators,
                )
        except Exception:
            # Print error message and move on to next machine
            error_message = traceback.format_exc()
            print(error_message)
            error_messages[machine["ipmi_ip"]] = error_message

    print_error_table(error_messages, file_path)

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
            cpu_list.append(cpu_info.dict)
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
    if memory_response.status == 200:
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
    storage_response = redfish_session.get(REDFISH_STORAGE_URI)

    drive_list = []
    if storage_response.status == 200:
        storage_summary = storage_response.dict
        for storage in storage_summary.get("Members", []):
            storage_info = redfish_session.get(storage["@odata.id"])
            for drive in storage_info.dict.get("Drives", []):
                drive_info = redfish_session.get(drive["@odata.id"])
                drive_list.append(drive_info.dict)

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
                                                drive_list.append(hp_drive_info.dict)
    return drive_list


def get_network(redfish_session: redfish.rest.v1.HttpClient) -> list:
    """Get nic and network port information from Redfish

    Args:
        redfish_session (Redfish HTTP Client): The Redfish client object

    Returns:
        nic_list, port_list (tuple): Information about network cards and ports
    """
    print("Getting Redfish network information:")
    network_response = redfish_session.get(REDFISH_NETWORK_URI)
    nic_list = []
    port_list = []
    eth_list = []
    if network_response.status == 200:
        network_summary = network_response.dict
        for nic in network_summary.get("Members", []):
            network_interface = redfish_session.get(nic["@odata.id"])
            if (
                "Links" in network_interface.dict
                and "NetworkAdapter" in network_interface.dict["Links"]
            ):
                network_adapter_endpoint = network_interface.dict["Links"][
                    "NetworkAdapter"
                ]["@odata.id"]
                nic_info = redfish_session.get(network_adapter_endpoint)
                nic_list.append(nic_info.dict)
                network_ports = nic_info.dict.get("NetworkPorts")
                if isinstance(network_ports, list):
                    ports_info = redfish_session.get(
                        nic_info.dict["NetworkPorts"][0]["@odata.id"]
                    )
                elif network_ports is not None:
                    ports_info = redfish_session.get(
                        nic_info.dict["NetworkPorts"]["@odata.id"]
                    )
                else:
                    ports_info = None
                if ports_info is not None:
                    for port in ports_info.dict.get("Members", []):
                        if "@odata.id" in port:
                            port_info = redfish_session.get(port["@odata.id"])
                            port_list.append(port_info.dict)
    ethernet_summary = redfish_session.get(REDFISH_SYSTEMS_ETHERNET_INTERFACES_URI)
    for eth in ethernet_summary.dict.get("Members", []):
        ethernet_interface = redfish_session.get(eth["@odata.id"])
        eth_list.append(ethernet_interface.dict)

    if port_list:
        return nic_list, port_list
    else:
        return nic_list, eth_list


def get_hostname(public_ip, sku, system_json):
    try:
        hostname = socket.gethostbyaddr(public_ip)[0]
    except socket.herror:
        if sku and "SKU" in system_json:
            print("DNS not working, using SKU as name instead")
            hostname = system_json["SKU"]
        else:
            print("DNS not working, using SerialNumber as name instead")
            hostname = system_json["SerialNumber"]
    return hostname


def get_accelerators(
    redfish_session: redfish.rest.v1.HttpClient, system_json: dict, processors: dict
) -> list:
    """Get nic and network port information from Redfish

    Args:
        redfish_session (Redfish HTTP Client): The Redfish client object
        system_json (dict): General information about the system
        processors (dict): Processors that belong to the system

    Returns:
        accelerators: Information about accelerators
    """
    print("Getting Redfish accelerator information:")
    accelerators = []
    # check under Processors
    for processor in processors:
        if processor.get("ProcessorType") == "FPGA":
            processor_pcie_functions = processor.get("Links", {}).get(
                "PCIeFunctions", []
            )
            if processor_pcie_functions:
                processor_pcie_function = redfish_session.get(
                    processor_pcie_functions[0]["@odata.id"]
                ).dict

                accelerators.append(
                    {
                        "name": processor["FPGA"]["Model"],
                        "manufacturer": processor["Manufacturer"],
                        "device_id": processor_pcie_function.get("DeviceId", ""),
                        "subsystem_device_id": processor_pcie_function.get(
                            "SubsystemDeviceId", ""
                        ),
                        "subsystem_vendor_id": processor_pcie_function.get(
                            "SubsystemVendorId", ""
                        ),
                        "vendor_id": processor_pcie_function.get("VendorId", ""),
                    }
                )

    # check under PCIDevices
    oem = system_json.get("Oem", {})
    links = {}
    if "Hpe" in oem:
        links = oem.get("Hpe", {}).get("Links", {})
    elif "Hp" in oem:
        links = oem.get("Hp", {}).get("Links", {})

    for link in links:
        if "PCIDevices" in link:
            pci_devices_response = redfish_session.get(links[link][0]["@odata.id"])
            pci_devices = pci_devices_response.dict
            for pci_device in pci_devices.get("Members", []):
                pci_device_response = redfish_session.get(pci_device["@odata.id"])
                pci_device = pci_device_response.dict
                pci_device_name = pci_device.get("Name", "")
                if "Accelerator" in pci_device_name or "GPU" in pci_device_name:
                    accelerators.append(
                        {
                            "name": pci_device_name,
                            # Use first word of device name as manufacturer
                            "manufacturer": pci_device_name.split(" ")[0],
                            # HP devices use 'ID' instead of 'Id'
                            "device_id": pci_device.get("DeviceID", ""),
                            "subsystem_device_id": pci_device.get(
                                "SubsystemDeviceID", ""
                            ),
                            "subsystem_vendor_id": pci_device.get(
                                "SubsystemVendorID", ""
                            ),
                            "vendor_id": pci_device.get("VendorID", ""),
                        }
                    )
    if not accelerators:
        # Avoid double-counting, check under PCIeFunctions if no accelerators elsewhere
        pcie_functions = system_json.get("PCIeFunctions", {})
        for pcie_function in pcie_functions:
            pcie_function_response = redfish_session.get(pcie_function["@odata.id"])
            pcie_function_info = pcie_function_response.dict
            if "ProcessingAccelerators" in pcie_function_info.get("DeviceClass", ""):
                if pcie_function_info["Status"]["State"] == "Enabled":
                    pcie_device_response = redfish_session.get(
                        pcie_function_info["Links"]["PCIeDevice"]["@odata.id"]
                    )
                    pcie_device = pcie_device_response.dict
                    accelerators.append(
                        {
                            "name": pcie_function_info.get("DeviceId", ""),
                            "manufacturer": pcie_device.get("Manufacturer", ""),
                            "device_id": pcie_function_info.get("DeviceId", ""),
                            "subsystem_device_id": pcie_function_info.get(
                                "SubsystemDeviceId", ""
                            ),
                            "subsystem_vendor_id": pcie_function_info.get(
                                "SubsystemVendorId", ""
                            ),
                            "vendor_id": pcie_function_info.get("VendorId", ""),
                        }
                    )
    return accelerators


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
    sku_for_dell: bool,
    lab_choice: str,
    accelerators
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
        sku_for_dell (bool): If sku's should be used for dell's
        lab_choice (str): The lab that the machine is located in
        accelerators (list): Information about accelerators in system
    """
    if sku_for_dell:
        if "dell" in system_json["Manufacturer"].lower():
            serial_number = system_json["SKU"]
        else:
            serial_number = system_json["SerialNumber"]
    else:
        if sku and "SKU" in system_json:
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
    if cpu_list:
        processors_id = check_and_post_processor(session, cpu_list, urls.CPU_URL, urls)
    locations_id = check_and_post(session, urls.LOCATION_URL, {"name": lab_choice})

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
        if glpi_computer["serial"] == serial_number and glpi_computer["uuid"] == uuid:
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
            computer_model_id,
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
    if cpu_list:
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
                {"name": name["Model"]},
            )

        vendor = 0
        if "Manufacturer" in name:
            if name["Manufacturer"]:
                vendor = name["Manufacturer"]
            else:
                vendor = "None"

        if "Id" in name:
            manufacturers_id = vendor
            if vendor:
                manufacturers_id = check_and_post(
                    session, urls.MANUFACTURER_URL, {"name": vendor}
                )
            nic_id = check_and_post(
                session,
                urls.DEVICE_NETWORK_CARD_URL,
                {
                    "designation": name["Id"],
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
            nic_ids[name["Id"]] = nic_item_id

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
            "name": name["Id"],
            "instantiation_type": "NetworkPortEthernet",
        }

        if "AssociatedNetworkAddresses" in name:
            additional_information = {"mac": name["AssociatedNetworkAddresses"][0]}
        elif "MACAddress" in name:
            additional_information = {"mac": name["MACAddress"]}
        else:
            additional_information = None
        network_port_id = check_and_post(
            session, urls.NETWORK_PORT_URL, search_criteria, additional_information
        )
        speed = 0
        try:
            speed = name["SpeedMbps"]
            if speed == None: speed = 0
        except KeyError:
            pass
        try:
            speed = name["SupportedLinkCapabilities"][0]["LinkSpeedMbps"]
        except KeyError:
            pass
        nic_id = ""
        if name["Id"] in nic_ids:
            nic_id = nic_ids[name["Id"]]
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
        if (
            ("Status" in ram and ram["Status"]["State"] == "Enabled")
            or ("DIMMStatus" in ram and ram["DIMMStatus"] == "GoodInUse")
        ) and ("GPU" not in ram.get("Name", "")):
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

    # Create accelerators
    post_accelerators(session, urls, accelerators, ACCELERATOR_IDS, COMPUTER_ID)


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
    computer_model_id: int,
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
        computer_model_id (int): ID of the computer's model
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
            session,
            field=location_details,
            urls=urls,
            computer_model_id=computer_model_id,
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
    computer_model_id: int,
) -> None:
    """Update a computer model's size if it doesn't match information from Sunbird

    Args:
        Session (Session object): The requests session object
        field (dict): Contains information about the rack location
        urls (common.urlinitialization.UrlInitialization): GLPI API URL's
        computer_model_id (int): ID of the computer model associated with the rack item
    """
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
    field = field[0]
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
    field = field[0]
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


def parse_list(args: argparse.Namespace, machines: list) -> list:
    """Reads machine information from the provided list and CLI args and runs the
    relevant command

    Args:
        args (argparse.Namespace): Arguments passed in by the user via the CLI
    """
    print("Parsing machine file\n")
    machine_list = ""
    try:
        f = open(args.machine_list, "r")
        machine_list = f.readlines()
        f.close()
    except FileNotFoundError:
        sys.exit("can't open %s" % (machine_list))

    for line in machine_list:
        if line[0] != "#":
            split_line = line.split(",")
            if len(split_line) == 5:
                machines.append(
                    {
                        "ipmi_ip": split_line[0],
                        "ipmi_username": split_line[1],
                        "ipmi_password": split_line[2],
                        "public_ip": split_line[3],
                        "lab_choice": split_line[4],
                    }
                )
            else:
                print("Line formatting incorrect, length is not 5:\n\t")
                print(split_line)
    return machines


def parse_machine_flags(args: argparse.Namespace) -> list:
    """Parses flags that specify machine information and creates list of machines to be
    imported

    Args:
        args (argparse.Namespace): Arguments passed in by the user via the CLI

    Returns:
        list: machines to be imported
    """
    machines = []
    missing_flags = []
    flags = {
        "ipmi_ip": args.ipmi_ip,
        "ipmi_username": args.ipmi_user,
        "ipmi_password": args.ipmi_pass,
        "public_ip": args.public_ip,
        "lab_choice": args.lab,
    }
    for flag, value in flags.items():
        if not value:
            missing_flags.append(flag)
    if missing_flags:
        print(
            "You haven't specified all of the flags to import a machine - you are "
            + f"missing the following flags: {', '.join(missing_flags)}. Checking for "
            + "a config file with machines to be imported..."
        )
    else:
        machines.append(flags)
    if args.machine_list:
        machines = parse_list(args, machines)
    elif not machines:
        raise Exception(
            "You need to specify a machine for import, either through "
            + "the commmand line flags --ipmi_ip, --ipmi_user, --ipmi_pass,"
            + "--public_ip, and -l/--lab, or via a csv file with -m."
        )
    return machines


# Executes main if run as a script.
if __name__ == "__main__":
    main()
