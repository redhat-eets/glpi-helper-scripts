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
import json
import requests
import pexpect
import common.format_dicts as format_dicts


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
    for glpi_fields in glpi_fields_list:
        for glpi_field in glpi_fields.json():
            if all(glpi_field[key] == value for key, value in search_criteria.items()):
                return glpi_field["id"]
    return None


def check_fields(session: requests.sessions.Session, url: str) -> list:
    """Method for getting the glpi fields at the given url

    Args:
        session (Session object): The requests session object
        url (str): The url to get the fields

    Returns:
        glpi_fields_list (list): The list of glpi fields at the URL
    """
    glpi_fields_list = []
    api_range = 0
    api_increment = 50
    more_fields = True
    while more_fields:
        range_url = (
            url + "?range=" + str(api_range) + "-" + str(api_range + api_increment)
        )
        glpi_fields = session.get(url=range_url)
        if (
            glpi_fields.json()
            and glpi_fields.json()[0] == "ERROR_RESOURCE_NOT_FOUND_NOR_COMMONDBTM"
        ):
            more_fields = False
            glpi_fields_list.append(glpi_fields)
        elif glpi_fields.json() and glpi_fields.json()[0] == "ERROR_RANGE_EXCEED_TOTAL":
            more_fields = False
        else:
            glpi_fields_list.append(glpi_fields)
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
    session: requests.sessions.Session, url: str, post_information: dict
) -> int:
    """A helper method to check the field at the given API endpoint (URL) and post
       the field if it is not present.

    Args:
        Session (Session object): The requests session object
        url (str): The url of the component to be populated
        post_information (dict): Dictionary containing the desired state of the glpi item.
            ex: {"glpi_field_name": glpi_field_value}
    Returns:
        id (int): the id of the field.
    """
    print("Checking GLPI fields:")
    # Check if the field is present at the URL endpoint.
    id = check_field(session, url, search_criteria=post_information)
    # Create a field if one was not found and return the ID.
    glpi_post = post_information
    id = create_or_update_glpi_item(session, url, glpi_post, id)
    print("Created/Updated GLPI field")
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

    for glpi_fields in glpi_fields_list:
        for glpi_field in glpi_fields.json():
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


def check_and_post_operating_system_item(
    session: requests.sessions.Session,
    url: str,
    operating_system_id: int,
    operating_system_version_id: int,
    operating_system_architecture_id: int,
    operating_system_kernel_version_id: int,
    item_id: int,
    item_type: str,
) -> int:
    """A helper method to check the operating system item field at the given API
       endpoint (URL) and post the field if it is not present. Takes in the session,
       field, and API url. Return the id of the field. NOTE: Operating systems have
       been moved to a different object than descibed (Item_OperatingSystem).
       This is undocumented except for issue 3334 on the glpi-project GitHub.

    Args:
        session (Session object): The requests session object
        url (str): GLPI API endpoint for the operating system item field
        operating_system_id (int): ID of the operating system in GLPI
        operating_system_version_id (int): ID of the operating system version in GLPI
        operating_system_architecture_id (int): ID of the operating system architecture
                                                in GLPI
        operating_system_kernel_version_id (int): ID of the operating system kernel
                                                  version in GLPI
        item_id (int): ID of the item (usually a computer) associated with the
                       operating system item
        item_type (str): Type of the item associated with the operating system item,
                         usually "Computer"

    Returns:
        id (int): ID of the operating system item in GLPI
    """
    # Check if the field is present at the URL endpoint.
    print("Checking GLPI OS fields:")
    id = check_field(
        session,
        url,
        search_criteria={
            "items_id": item_id,
            "itemtype": item_type,
            "operatingsystems_id": operating_system_id,
        },
    )

    # Create a field if one was not found and return the ID.
    print("Creating GLPI OS Item field:")
    glpi_post = {
        "items_id": item_id,
        "itemtype": item_type,
        "operatingsystems_id": operating_system_id,
        "operatingsystemversions_id": operating_system_version_id,
        "operatingsystemarchitectures_id": operating_system_architecture_id,
        "operatingsystemkernelversions_id": operating_system_kernel_version_id,
    }

    id = create_or_update_glpi_item(session, url, glpi_post, id)

    return id


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


def check_and_post_network_port_ethernet(
    session: requests.sessions.Session,
    url: str,
    network_port_id: int,
    speed: str,
    nic: str,
) -> int:
    """A helper method to check the network port ethernet field at the given API
       endpoint (URL) and post the field if it is not present.

    Args:
        session (Session object): The requests session object
        url (str): GLPI API endpoint for network port ethernet field
        network_port_id (int): ID of the network port that the ethernet is associated
                               with
        speed (str): Speed that the port is capable of
        nic (str): ID of the network card that the ethernet field is associated with

    Returns:
        id (int): GLPI ID of network port ethernet
    """
    # Check if the field is present at the URL endpoint.
    print("Checking GLPI Network Port Ethernet fields:")

    id = check_field(session, url, search_criteria={"networkports_id": network_port_id})

    print("Creating GLPI Network Port Ethernet field:")
    glpi_post = {"networkports_id": network_port_id}
    if nic is not None:
        glpi_post["items_devicenetworkcards_id"] = nic
    if speed != 0:
        glpi_post["speed"] = speed

    id = create_or_update_glpi_item(session, url, glpi_post, id)

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

    for glpi_fields in glpi_fields_list:
        for glpi_field in glpi_fields.json():
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

    for glpi_fields in glpi_fields_list:
        for glpi_field in glpi_fields.json():
            if glpi_field["items_id"] == item_id:
                removed = session.delete(url + str(glpi_field["id"]))
                print(str(removed) + "\n")
                break
    return


def check_and_post_disk_item(
    session: requests.sessions.Session,
    url: str,
    item_id: int,
    item_type: str,
    disk_name: str,
    size: int,
    partition: str = None,
) -> None:
    """A helper method to check the disk item field at the given API endpoint (URL)
       and post the field if it is not present.

    Args:
        session (Session object): The requests session object
        url (str): GLPI API endpoint for the disk item field
        item_id (int): ID of the item (usually a computer) associated with the disk
                       item
        item_type (str): Type of the item associated with the disk item, usually
                         "Computer"
        disk_name (str): Name of disk item
        size (int): Capacity of disk item in MB
        partition (str): Mountpoint of the disk item
    """
    # Check if the field is present at the URL endpoint.
    print("Checking GLPI Disk Item fields:")
    id = check_field(
        session,
        url,
        search_criteria={"items_id": item_id, "itemtype": item_type, "name": disk_name},
    )

    # Create a field if one was not found and return the ID.
    print("Creating GLPI Disk Item field:")
    glpi_post = {
        "items_id": item_id,
        "itemtype": item_type,
        "name": disk_name,
        "totalsize": size,
    }
    if partition is not None:
        glpi_post["mountpoint"] = partition
    id = create_or_update_glpi_item(session, url, glpi_post, id)

    return


def print_final_help() -> None:
    """Print the final usage help for the user"""
    print(
        "Script completed, see responses for any issues.\n\nNOTE: Please "
        + "verify correct information in GLPI.\n"
    )


def get_computers(session: requests.sessions.Session, urls: UrlInitialization) -> list:
    """Method for getting all computers

    Args:
        session (Session object):        the requests session object
        urls (UrlInitialization object): the URL object

    Returns:
        list: computers from GLPI
    """
    print("Getting computer information:\n")

    computers = []

    computer_json = check_fields(session, urls.COMPUTER_URL)
    for computer_list in computer_json:
        for computer in computer_list.json():
            computers.append(json.dumps(computer))
    return computers


def get_network_equipment(
    session: requests.sessions.Session, urls: UrlInitialization
) -> list:
    """Method for getting all network equipment

    Args:
        session (Session object):        the requests session object
        urls (UrlInitialization object): the URL object

    Returns:
        list: network equipment from GLPI
    """
    print("Getting computer information:\n")

    network_equipment_output = []

    network_equipment_json = check_fields(session, urls.NETWORK_EQUIPMENT_URL)
    for network_equipment_list in network_equipment_json:
        for network_equipment in network_equipment_list.json():
            network_equipment_output.append(json.dumps(network_equipment))
    return network_equipment_output


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
    # print("Getting reservation information:\n")

    reservations_output = ""

    reservation_json = check_fields(session, urls.RESERVATION_URL)
    if reservation_json:
        for reservation_list in reservation_json:
            for reservation in reservation_list.json():
                reservation_item_json = check_field_without_range(
                    session,
                    (
                        urls.RESERVATION_ITEM_URL
                        + str(reservation["reservationitems_id"])
                    ),
                )
                user_json = check_field_without_range(
                    session, (urls.USER_URL + str(reservation["users_id"]))
                )

                # If searching for specific user, only select
                # reservations with that username.
                if user and user.lower() not in user_json["name"].lower():
                    continue

                item_json = check_field_without_range(
                    session,
                    urls.BASE_URL
                    + reservation_item_json["itemtype"]
                    + "/"
                    + str(reservation_item_json["items_id"]),
                )

                # If searching for specific hostname, only select
                # reservations with that hostname.
                if hostname and hostname != item_json["name"]:
                    continue

                reservations_output += (
                    "Reservation " + str(reservation["id"]) + ":" + "\n"
                )
                reservations_output += (
                    "  User "
                    + str(reservation["users_id"])
                    + ": "
                    + user_json["name"]
                    + "\n"
                )
                reservations_output += (
                    "  "
                    + reservation_item_json["itemtype"]
                    + " "
                    + str(reservation_item_json["items_id"])
                    + ": "
                    + item_json["name"]
                    + "\n"
                )
                reservations_output += "  Begins: " + str(reservation["begin"]) + "\n"
                reservations_output += "  Ends: " + str(reservation["end"]) + "\n"

                if reservation["comment"]:
                    reservations_output += (
                        '  Comment: "' + reservation["comment"] + '"\n\n'
                    )
                else:
                    reservations_output += "  Comment: N/A \n\n"
    else:
        reservations_output += "\tNo reservations.\n"
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
        id = post_response.json()["id"]
    else:
        post_response = session.put(url=url, json={"input": glpi_post})
    print(str(post_response) + "\n")

    return id


def error(message):
    print("Error: " + message + "\nAborting.\n")
    exit()
