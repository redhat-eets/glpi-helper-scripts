"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: utils.py                                                        |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: Common utility functions for use in filtering, population,      |
|              and reservation scripts                                         |
|                                                                              |
|------------------------------------------------------------------------------|
"""

from common.urlinitialization import UrlInitialization
from common.switches import Switches
import requests
import pexpect
import os
import yaml
import common.format_dicts as format_dicts
from prettytable import PrettyTable


def check_field(
    session: requests.sessions.Session,
    url: str,
    search_criteria: dict,
) -> str:
    """Method for getting the glpi fields at the given url and checking if a
       specific field exists.

    Args:
        session (Session object): The requests session object
        url (str):                The url to get the fields
        search_criteria (dict):   A dictionary of criteria to match w/ GLPI fields.

    Returns:
        (str): The field ID if found, None otherwise
    """
    glpi_fields_list = check_fields(session, url)
    # Check if the field is present at the URL endpoint.
    for glpi_field in glpi_fields_list:
        if all(glpi_field[key] == value for key, value in search_criteria.items()):
            return glpi_field["id"]
    return None


def check_fields(
    session: requests.sessions.Session,
    url: str,
    params: dict = {},
) -> list:
    """Method for getting the glpi fields at the given url

    Args:
        session (Session object): The requests session object
        url (str): The url to get the fields
        params (dict): The parameters to pass to the url
    Returns:
        glpi_fields_list (list): The list of glpi fields at the URL
    """
    glpi_fields_list = []
    api_range = 0
    api_increment = 10000
    more_fields = True
    while more_fields:
        params.update({"range": f"{api_range}-{api_range + api_increment}"})
        glpi_fields = session.get(url=url, params=params).json()
        if "search" in url and "data" in glpi_fields:
            glpi_fields = glpi_fields["data"]
            
            # If Search isn't set up for this object, raise error
            if not glpi_fields[0]:
                raise ValueError((f"Search isn't set up in the GLPI API for this object: {url}."
                 "Please use the traditional API endpoint instead."))

        if glpi_fields and glpi_fields[0] == "ERROR_RESOURCE_NOT_FOUND_NOR_COMMONDBTM":
            more_fields = False
            glpi_fields_list.extend(glpi_fields)
        elif glpi_fields and glpi_fields[0] == "ERROR_RANGE_EXCEED_TOTAL":
            more_fields = False
        else:
            glpi_fields_list.extend(glpi_fields)
            api_range += api_increment

    return glpi_fields_list


def check_field_without_range(session: requests.sessions.Session, url: str) -> list:
    """Method for getting the glpi fields at the given url (without
       ranges/lists)

    Args:
        session (Session object): The requests session object
        url (str): The url to get the fields

    Returns:
        glpi_fields (list[json]): The glpi fields at the URL
    """
    glpi_fields = session.get(url=url)
    return glpi_fields.json()


def check_and_post(
    session: requests.sessions.Session,
    url: str,
    search_criteria: dict,
    additional_information: dict = None,
) -> int:
    """A helper method to check the field at the given API endpoint (URL) and post
       the field if it is not present.

    Args:
        Session (Session object): The requests session object
        url (str): The url of the component to be populated
        search_criteria (dict): Dictionary containing the desired state of the GLPI
            item. It should contain fields to use when checking GLPI for pre-existing
            items. For example: {"name": "glpi_field_value"} will check GLPI for
            existing items named "glpi_field_value". The same dictionary
            ({"name": "glpi_field_value"}) will be used to import this item into GLPI,
            via either a PUT or POST request, after it's combined with
            additional_information.
        additional_information (dict): Dictionary containing fields that
            shouldn't be used to check GLPI, but should be sent in the POST and PUT
            requests. For example, when using check_and_post() for racks, you would pass
            the background color under "additional_information". If a rack's name, ID,
            and location were all the same, but its color was different, a new rack
            should NOT be created, as that isn't a characteristic that helps identify a
            unique rack. Instead, the existing rack should be updated in place.

    Returns:
        id (int): the id of the field.
    """
    print(f"Checking GLPI fields for {url}:")
    # Check if the field is present at the URL endpoint.
    id = check_field(session, url, search_criteria)

    # Create a field if one was not found and return the ID.
    if additional_information is not None:
        search_criteria.update(additional_information)
    if id is not None:
        search_criteria.update({"id": id})
    id = create_or_update_glpi_item(session, url, search_criteria, id)
    return id


def check_and_post_processor(
    session: requests.sessions.Session, field: dict, url: str, urls: UrlInitialization
) -> int:
    """A helper method to check the processor field at the given API endpoint (URL)
       and post the field if it is not present. NOTE: The CPU API has differing fields
       (designation instead of name, extra fields to populate, and misspelled fields:
       "frequence" should clearly be "frequency"]).

    Args:
        Session (Session object): The requests session object
        field (dict): Contains information about the CPU
        url (str): GLPI API endpoint for the processor field
        urls (UrlInitialization object): the URL object

    Returns:
        id (int): ID of the processor in GLPI
    """
    print("Checking GLPI CPU fields:")
    # Check if the field is present at the URL endpoint.
    id = check_field(session, url, search_criteria={"designation": field["Model name"]})
    # Create a field if one was not found and return the ID.
    if id is None:
        # Get the manufacturer or create it (NOTE: This may create duplicates
        # with slight variation)
        manufacturers_id = check_and_post(
            session, urls.MANUFACTURER_URL, {"name": field["Vendor ID"]}
        )
        print("Creating GLPI CPU field:")
        glpi_post = {
            "designation": field["Model name"],
            "nbcores_default": field["Core(s) per socket"],
            "nbthreads_default": (
                int(field["Thread(s) per core"]) * int(field["Core(s) per socket"])
            ),
            "manufacturers_id": manufacturers_id,
        }
        post_response = session.post(url=url, json={"input": glpi_post})
        print(str(post_response) + "\n")
        id = post_response.json()["id"]

    return id


def check_and_post_processor_item(
    session: requests.sessions.Session,
    field: dict,
    url: str,
    item_id: int,
    processor_id: int,
    item_type: str,
    sockets: int,
) -> None:
    """A helper method to check the processor item field at the given API endpoint
       (URL) and post the field if it is not present. NOTE: The CPU Item API differs
       from the regular Processor component API. This is where it is associated with
       the "item" (the computer). The field names also differ from the normal processor
       API, even if they are repeated.

    Args:
        session (Session object): The requests session object
        field (dict): Contains information about the CPU
        url (str): GLPI API endpoint for the processor item field
        item_id (int): GLPI ID of the item (usually a computer) associated with the
                       processor
        processor_id (int): GLPI ID of the processor
        item_type (str): Type of the item associated with the processor item, usually
                         "Computer"
        sockets (int): Number of sockets
    """
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
        "nbcores": field["Core(s) per socket"],
        "nbthreads": (
            int(field["Thread(s) per core"]) * int(field["Core(s) per socket"])
        ),
    }
    for id in ids:
        post_response = session.put(url=url, json={"input": glpi_post})
        print(str(post_response) + "\n")
    for i in range(sockets - len(ids)):
        post_response = session.post(url=url, json={"input": glpi_post})
        print(str(post_response) + "\n")

    return


def check_and_post_network_port(  # noqa: C901
    session: requests.sessions.Session,
    url: str,
    item_id: int,
    item_type: str,
    port_number: str,
    name: str,
    instantiation_type: str,
    network: list,
    switch_dict: dict,
    urls: UrlInitialization,
    switch_info: Switches,
) -> int:
    """A helper method to check the network port field at the given API endpoint
       (URL) and post the field if it is not present.

    Args:
        session (Session object): The requests session object
        url (str): GLPI API endpoint for the network port field
        item_id (int): ID of the item (usually a computer) associated with the
                       operating system item
        item_type (str): Type of the item associated with the operating system item,
                         usually "Computer"
        port_number (str): Number of port, which is adjusted incrementally
        name (str): Name of port
        instantiation_type (str): Type of the instantiation, usually
                                  'NetworkPortEthernet'
        network (list): Details of network port
        switch_dict (dict): Dictionary of switch details
        urls (UrlInitialization object): the URL object
        switch_info (Switches object): Contains information about lab switches

    Returns:
        id (int): ID of the network port in GLPI
    """
    # Check if the field is present at the URL endpoint.
    print("Checking GLPI Network Port fields:")
    id = check_field(
        session,
        url,
        search_criteria={
            "items_id": item_id,
            "itemtype": item_type,
            "logical_number": port_number,
            "name": name,
            "instantiation_type": instantiation_type,
        },
    )

    # Create a field if one was not found and return the ID.
    glpi_post = {
        "items_id": item_id,
        "itemtype": item_type,
        "logical_number": port_number,
        "name": name,
        "instantiation_type": instantiation_type,
    }
    if network is not None:
        for line in network:
            if line[0] == "ether":
                glpi_post["mac"] = line[1]
                break
    id = create_or_update_glpi_item(session, url, glpi_post, id)

    # Attempt to connect the network ports.
    if "mac" in glpi_post:
        for lab in switch_info.switch_map.keys():
            for switch_ip in switch_info.switch_map[lab]["switches"].keys():
                if "name" in switch_info.switch_map[lab]["switches"][switch_ip]:
                    switch_name = switch_info.switch_map[lab]["switches"][switch_ip][
                        "name"
                    ]
                    if switch_ip not in switch_dict:
                        switch_dict[switch_ip] = [
                            switch_name,
                            get_switch_ports(
                                lab,
                                switch_ip,
                                switch_info,
                            ),
                        ]
                    if glpi_post["mac"] in switch_dict[switch_ip][1]:
                        print(switch_dict[switch_ip][1][glpi_post["mac"]])
                        check_and_post_network_port_network_port(
                            session,
                            id,
                            urls.NETWORK_EQUIPMENT_URL,
                            urls.NETWORK_PORT_URL,
                            urls.NETWORK_PORT_NETWORK_PORT_URL,
                            switch_dict[switch_ip][0],
                            switch_dict[switch_ip][1][glpi_post["mac"]],
                        )

    return id


def check_and_post_network_port_network_port(  # noqa: C901
    session: requests.sessions.Session,
    server_network_port_id: int,
    network_equipment_url: str,
    network_port_url: str,
    network_port_network_port_url: str,
    switch_name: str,
    switch_port: str,
) -> int:
    """A helper method to check the network port to network port field at the given
       API endpoint (URL) and post the field if it is not present. Takes in the
       session, field, and API url. Return the id of the field.

    Args:
        session (Session object): The requests session object
        server_network_port_id (int): ID of the server network port
        network_equipment_url (str):  GLPI API endpoint for the network equipment field
        network_port_url (str): GLPI API endpoint for the network port field
        network_port_network_port_url (str): GLPI API endpoint for the network port
                                             network port field
        switch_name (str): Name of the associated switch
        switch_port (str): MAC address of the associated switch

    Returns:
        id (int): ID of the network port network port in GLPI
    """
    # Check if the field is present at the URL endpoint.
    print("Checking GLPI Network Equipment fields:")
    switch_id = check_field(
        session, network_equipment_url, search_criteria={"name": switch_name}
    )

    switch_port_id = check_field(
        session,
        network_port_url,
        search_criteria={
            "itemtype": "NetworkEquipment",
            "items_id": switch_id,
            "name": switch_port,
        },
    )

    if switch_port_id:
        # Check if the field is present at the URL endpoint.
        print("Checking GLPI Network Port to Network Port Ethernet fields:")
        id = check_field(
            session,
            network_port_network_port_url,
            search_criteria={
                "networkports_id_1": server_network_port_id,
                "networkports_id_2": switch_port_id,
            },
        )

        print("Creating GLPI Network Port to Network Port Ethernet field:")
        glpi_post = {
            "networkports_id_1": server_network_port_id,
            "networkports_id_2": switch_port_id,
        }
        id = create_or_update_glpi_item(
            session, network_port_network_port_url, glpi_post, id
        )

        return id
    else:
        print(
            "Error: \n\tCould not connect server interface "
            + str(server_network_port_id)
            + " to switch "
            + switch_name
            + "."
        )
        return


def check_and_post_device_memory_item(
    session: requests.sessions.Session,
    url: str,
    item_id: int,
    item_type: str,
    memory_id: int,
    size: int,
    quantity: int,
) -> None:
    """A helper method to check the device memory item field at the given API
       endpoint (URL) and post the field if it is not present.

    Args:
        session (Session object): The requests session object
        url (str): GLPI API endpoint for the memory item field
        item_id (int): ID of the item (usually a computer) associated with the memory
                       item
        item_type (str): Type of the item associated with the memory item, usually
                         "Computer"
        memory_id (int): ID of the memory field
        size (int): Size of memory item in MB
        quantity (int): Number of memory items
    """
    # Check if the field is present at the URL endpoint.
    print("Checking GLPI Memory Item fields:")
    ids = []
    glpi_fields_list = check_fields(session, url)

    for glpi_field in glpi_fields_list:
        if (
            glpi_field["items_id"] == item_id
            and glpi_field["itemtype"] == item_type
            and glpi_field["devicememories_id"] == memory_id
            and glpi_field["size"] == size
        ):
            ids.append(glpi_field["id"])
            if len(ids) == quantity:
                break
    # Create a field if one was not found and return the ID.
    print("Creating GLPI Memory Item field:")
    glpi_post = {
        "items_id": item_id,
        "itemtype": item_type,
        "devicememories_id": memory_id,
        "size": size,
    }

    for id in ids:
        post_response = session.put(url=url, json={"input": glpi_post})
        print(str(post_response) + "\n")
    for i in range(quantity - len(ids)):
        post_response = session.post(url=url, json={"input": glpi_post})
        print(str(post_response) + "\n")

    return


def get_unspecified_device_memory(
    session: requests.sessions.Session, url: str, designation: str
) -> int:
    """Get memory items of 'Unspecified' type, which may have been populated using
       the Redfish creation script.

    Args:
        session (Session object): The requests session object
        url (str): GLPI API endpoint for the device memory item
        designation (str): Name of memory device, usually 'Unspecified'

    Returns:
        id (int): ID of the unspecified memory item in GLPI
    """
    # Check if the field is present at the URL endpoint.
    print("Checking GLPI Memory fields to remove Unspecified:")
    id = check_field(
        session,
        url,
        search_criteria={"designation": designation, "frequence": designation},
    )
    return id


def check_and_remove_unspecified_device_memory_item(
    session: requests.sessions.Session, url: str, item_id: int
) -> None:
    """Check and remove unspecified device memory items from GLPI

    Args:
        session (Session object): The requests session object
        url (str): GLPI API endpoint for the device memory item field
        item_id (int): ID of the unspecified device memory item in GLPI
    """
    # Check if the field is present at the URL endpoint.
    print("Checking GLPI Memory fields to remove Unspecified:")
    glpi_fields_list = check_fields(session, url)

    for glpi_field in glpi_fields_list:
        if glpi_field["items_id"] == item_id:
            removed = session.delete(url + str(glpi_field["id"]))
            print(str(removed) + "\n")
            break
    return


def print_final_help() -> None:
    """Print the final usage help for the user"""
    print(
        "Script completed, see responses for any issues.\n\nNOTE: Please "
        + "verify correct information in GLPI.\n"
    )


def get_reservations(
    session: requests.sessions.Session,
    urls: UrlInitialization,
    hostname: str = None,
    user: str = None,
) -> str:
    """Method for printing all reservation_split to stdout

    Args:
        session (Session object):        the requests session object
        urls (UrlInitialization object): the URL object
        hostname (str):                  Name of computer to search for
        user (str):                      Name of user to search for

    Returns:
        list: reservations from GLPI
    """
    print("Getting reservation information:")
    reservations_output = {}
    
    # Get All Information about Reservation
    payload = {
        "forcedisplay[0]": "1",
        "forcedisplay[1]": "2",
        "forcedisplay[2]": "3",
        "forcedisplay[3]": "4",
        "forcedisplay[4]": "5",
        "forcedisplay[5]": "6",
        "forcedisplay[6]": "7",
        "forcedisplay[7]": "8",

    }

    if user and not hostname:
        payload.update(
            {
                "criteria[0][field]": "6",
                "criteria[0][searchtype]": "contains",
                "criteria[0][value]": user.lower(),
            }
        )

    if hostname and not user:
        payload.update(
            {
                "criteria[0][field]": "1",
                "criteria[0][searchtype]": "contains",
                "criteria[0][value]": hostname.lower(),
            }
        )

    if user and hostname:
        payload.update(
            {
                "criteria[0][field]": "1",
                "criteria[0][searchtype]": "contains",
                "criteria[0][value]": hostname.lower(),
                "criteria[1][link]": "AND",
                "criteria[1][field]": "6",
                "criteria[1][searchtype]": "contains",
                "criteria[1][value]": user.lower(),
            }
        )

    reservation_json = check_fields(
        session, urls.SEARCH_RESERVATION_URL, params=payload
    )
    if reservation_json:
        reservations_output = {
            f"Reservation {reservation['2']}": {
                f"User {reservation['6']}": reservation["7"],
                f"Computer {reservation['3']}": reservation["1"],
                f"Begins": reservation["4"],
                f"Ends": reservation["5"],
                f"Comment": reservation["8"],
            }
            for reservation in reservation_json
        }
    else:
        reservations_output = "No reservations."
    return reservations_output

def get_switch_ports(lab: str, switch: str, switch_info: Switches) -> dict:
    """A helper method to get switch ports via ssh from the switch IP address
       input. After logging into the switch use the global switch command and call
       the stip helper method.

    Args:
        lab (str): The lab of the switch
        switch (str): IP address of switch
        switch_info (Switches object): Contains information about lab switches

    Returns:
        switch_output_dict (dict): Dictionary of switch ports
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
        child.sendline(switch_info.BRCTL_SHOWMACS_SWITCH_COMMAND)
        child.expect(terminal_prompt, timeout=30)
        switch_output_dict = format_dicts.strip_brctl_showmacs_switch_dict(
            child.after.strip(), "\n"
        )
        child.sendline("$?")
        child.expect(terminal_prompt, timeout=30)
        exit_code = child.after.strip().decode()
        if "127" in exit_code:
            print(
                "Error running command on Cumulus switch: "
                + switch_info.BRCTL_SHOWMACS_SWITCH_COMMAND
            )
    elif switch_type == "dell":
        child.sendline(switch_info.SHOW_MAC_ADDRESS_TABLE_SWITCH_COMMAND)
        child.expect(terminal_prompt, timeout=30)
        switch_output_dict = format_dicts.strip_show_mac_address_table_switch_dict(
            child.after.strip(), "\t"
        )
    else:
        print("Switch type unsupported: " + switch_type)
    child.sendline("exit")

    return switch_output_dict


def create_or_update_glpi_item(
    session: requests.sessions.Session, url: str, glpi_post: dict, id: int
) -> int:
    """Creates or updates a GLPI Item field based on the id_found flag.

    Args:
        session (Session object): The requests session object
        url (str): GLPI API endpoint for the operating system item field
        glpi_post (dict): Dictionary containing the GLPI data to post or update
        id (int): The current ID value

    Returns:
        id (int): ID of the created or updated operating system item in GLPI
    """
    if id is None:
        post_response = session.post(url=url, json={"input": glpi_post})
        try:
            id = post_response.json()["id"]
        except TypeError as e:
            e.add_note(f"Couldn't post item because of: {post_response.json()}")
            raise
        print(f"Created item at {url}")
    else:
        post_response = session.put(url=url, json={"input": glpi_post})
        print(f"Updated item at {url}")
    print(str(post_response) + "\n")

    return id


def error(message):
    print("Error: " + message + "\nAborting.\n")
    exit()


def print_error_table(error_messages: dict, file_path: str = "") -> None:
    """Takes errors generated by imports and prints formatted table with BMC IP's
    and their corresponding errors.

    Args:
        error_messages (dict[str, str]): Dictionary of Machines and their errors
    """
    if error_messages:
        table = PrettyTable()
        table.field_names = ["Machines", "Error Message"]
        for error in error_messages:
            table.add_row([error, error_messages[error]])
        table.align = "l"
        print(table)
        if file_path:
            print(f"Writing error table to {file_path}")
            with open(file_path, "w") as file:
                file.write(str(table))
    else:
        print("No errors detected!")
        print("\n")


def check_computer_reservable(session: str, link: str) -> bool:
    """Check that computer is reservable

    Args:
        session (str): the user's GLPI API token
        link (str):       the GLPI link to the machine to check

    Returns:
        True: on reservable, False otherwise
    """
    computer_reservable = check_field_without_range(
        session, link["href"].replace("/glpi", "")
    )
    if computer_reservable:
        for reservation_info in computer_reservable:
            if reservation_info["is_active"]:
                return True

    return False


def post_accelerators(
    session: requests.sessions.Session,
    urls: UrlInitialization,
    accelerators: list,
    accelerator_ids: dict,
    computer_id: str,
):
    """Update accelerators of machine in GLPI

    Args:
        session (requests.sessions.Session): requests object
        urls (UrlInitialization): UrlInitialization object
        accelerators (list): All accelerators found in Redfish
        accelerator_ids (dict): Manual mapping of device ID's to device names
        computer_id (str): ID of Computer in GLPI
    """
    for accelerator in accelerators:
        accelerator = clean_accelerator_data(accelerator, accelerator_ids)
        manufacturers_id = check_and_post(
            session,
            urls.MANUFACTURER_URL,
            {"name": accelerator["manufacturer"]},
        )
        if accelerator["vendor_id"]:
            check_and_post(
                session,
                urls.REGISTERED_ID_URL,
                {
                    "device_type": "PCI",
                    "itemtype": "Manufacturer",
                    "items_id": manufacturers_id,
                    "name": accelerator["vendor_id"],
                },
            )
        pci_model_id = check_and_post(
            session,
            urls.DEVICE_PCI_MODEL_URL,
            {"name": accelerator["name"]},
        )
        pcie_id = check_and_post(
            session,
            urls.DEVICE_PCI_URL,
            {
                "devicepcimodels_id": pci_model_id,
                "manufacturers_id": manufacturers_id,
                "designation": accelerator["name"],
            },
            {
                "subsystemdeviceidfield": accelerator["subsystem_device_id"],
                "subsystemvendoridfield": accelerator["subsystem_vendor_id"],
            },
        )
        if accelerator["device_id"]:
            check_and_post(
                session,
                urls.REGISTERED_ID_URL,
                {
                    "device_type": "PCI",
                    "itemtype": "DevicePci",
                    "items_id": pcie_id,
                    "name": accelerator["device_id"],
                },
            )
        check_and_post(
            session,
            urls.DEVICE_PCI_ITEM_URL,
            {
                "items_id": computer_id,
                "itemtype": "Computer",
                "devicepcis_id": pcie_id,
            },
        )


def clean_accelerator_data(accelerator: dict, accelerator_ids: dict) -> dict:
    """Clean accelerator information from Redfish to GLPI

    Args:
        accelerator (dict): All accelerators found in Redfish
        accelerator_ids (dict): Manual mapping of device ID's to device names

    Returns:
        _type_: _description_
    """
    # map ID to name
    if "0x" in accelerator["name"]:
        accelerator["name"] = accelerator_ids[accelerator["name"].lower()[2:]]
    # ZT Systems don't report manufacturer in English, only in code (8086XXX)
    if "8086" in accelerator["manufacturer"] and accelerator["vendor_id"] == "0x8086":
        accelerator["manufacturer"] = "Intel Corporation"
    # convert all id's to hex
    for key in accelerator:
        if accelerator[key] and "id" in key:
            if "0x" not in str(accelerator[key]):  # Ensure it's not already hex
                accelerator[key] = hex(accelerator[key])
    return accelerator


def parse_config_yaml(config_file) -> dict:
    """Process the config file, which can be passed as an env var or as a file

    Args:
        config_file (string): path to LDAP config YAML/JSON file or name of env var
        that contains config data as a string

    Returns:
        dict: Config file transformed into python dictionary
    """
    # Process General Config
    if os.path.isfile(config_file):
        # Process YAML/JSON file
        with open(config_file, "r") as config_path:
            group_map = yaml.safe_load(config_path)
    else:
        # Process env var
        yaml_content = os.getenv(config_file, "{}")
        group_map = yaml.safe_load(yaml_content)

    return group_map
