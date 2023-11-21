"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: format_dicts.py                                                 |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: Utility functions to format command output into dictionaries.   |
|                                                                              |
|------------------------------------------------------------------------------|
"""

import pexpect


def strip_dict(dict: list, delimiter: str) -> dict:
    """A helper method to strip whitespace, decode and split a dictionary.

    Args:
        dict (list): Contains information that needs to be decoded and split into a
                     dictionary
        delimiter (str): Text to split the information on
    Returns:
        stripped_dict (dict): Contains decoded and split information
    """
    stripped_dict = {}
    for entry in dict:
        temp = entry.lstrip().strip().decode().split(delimiter)
        for item in range(len(temp)):
            temp[item] = temp[item].lstrip().strip()
        if len(temp) > 1:
            stripped_dict[temp[0]] = temp[1]

    return stripped_dict


def strip_decoded_dict(dict: str, delimiter: str) -> dict:
    """A helper method to strip whitespace and split a dictionary (without decoding).

    Args:
        dict (str): Information to be stripped and split into a dictionary
        delimiter (str): Text to split the information on

    Returns:
        stripped_dict (dict): Contains stripped and split information
    """
    stripped_dict = {}
    dict = dict.split("\n")
    for entry in dict:
        temp = entry.lstrip().strip().split(delimiter)
        for item in range(len(temp)):
            temp[item] = temp[item].lstrip().strip().replace('"', "")
        if len(temp) > 1:
            stripped_dict[temp[0]] = temp[1]

    return stripped_dict


def strip_network_dict(dict: str, delimiter: str, coreos: bool = False) -> dict:
    """A helper method to strip whitespace and split a dictionary (without decoding)
       of network items.

    Args:
        dict (str): Information to be stripped and split into a dictionary
        delimiter (str): Text to split the information on
        coreos (bool): If the script is running on a coreos system

    Returns:
        stripped_dict (dict): Contains stripped and split information
    """
    stripped_dict = {}
    if coreos:
        dict = dict.split("\r\n\r\n")
    else:
        dict = dict.split("\n\n")
    for entry in dict:
        temp = entry.lstrip().strip().split(delimiter)
        for item in range(len(temp)):
            temp[item] = temp[item].lstrip().strip().replace('"', "")
        if len(temp) > 1:
            new_list = []
            for line in temp[1].splitlines():
                new_list.append(line.lstrip().strip().split())
            if coreos:
                if "\r\n" in temp[0]:
                    temp[0] = temp[0].split("\r\n")[1]
            stripped_dict[temp[0]] = new_list

    if not coreos:
        if "ovirtmgmt" in stripped_dict:
            del stripped_dict["ovirtmgmt"]
    return stripped_dict


def strip_ram_dict(dict: str, delimiter: str) -> dict:
    """A helper method to strip whitespace and split a dictionary (without decoding)
       of ram items.

    Args:
        dict (str): Information to be stripped and split into a dictionary
        delimiter (str): Text to split the information on

    Returns:
        stripped_dict (dict): Contains stripped and split information
    """
    stripped_dict = {}
    dict = dict.split("\n\n")
    dict.pop(0)
    for entry in dict:
        temp = entry.lstrip().strip().split("\n")
        key = temp[0]
        stripped_dict[key] = {}
        temp.pop(0)
        temp.pop(0)
        for item in temp:
            item = item.strip().split(delimiter)
            if len(item) > 1:
                stripped_dict[key][item[0]] = item[1]

    return stripped_dict


def strip_ram_dict_coreos(dict: str) -> dict:
    """A helper method to strip whitespace and split a dictionary (without decoding)
       of ram items.

    Args:
        dict (str): Information to be stripped and split into a dictionary

    Returns:
        stripped_dict (dict): Contains stripped and split information
    """
    stripped_dict = {}
    dict = dict.split("\n")
    for entry in dict:
        temp = entry.lstrip().strip().split()
        key = temp[0]
        stripped_dict[key] = temp[1]

    return stripped_dict


def strip_disks_dict(dict: str, delimiter: str) -> dict:
    """A helper method to strip whitespace and split a dictionary (without decoding)
       of disk items.

    Args:
        dict (str): Information to be stripped and split into a dictionary
        delimiter (str): Text to split the information on

    Returns:
        stripped_dict (dict): Contains stripped and split information
    """
    stripped_dict = {}
    dict = dict.split("\n\n")
    # Remove odd entries from the list, per https://stackoverflow.com/a/28883784
    del dict[1::2]

    i = 0
    for entry in dict:
        key = ""
        temp = entry.lstrip().strip().split("\n")
        for item in temp:
            split_item = item.strip().split(delimiter)
            if split_item[0] == "Model":
                key = str(i) + ": " + split_item[1]
                stripped_dict[key] = {}
                i += 1
            elif len(split_item) > 1:
                if split_item[0][0:4] == "Disk" and (
                    len(split_item[0]) < 10 or split_item[0][5:10] != "Flags"
                ):
                    stripped_dict[key]["Size"] = split_item[1]
                    stripped_dict[key]["Part"] = split_item[0][5:]
                else:
                    stripped_dict[key][split_item[0]] = split_item[1]

    return stripped_dict


def strip_disks_dict_coreos(dict: str, delimiter: str) -> dict:
    """A helper method to strip whitespace and split a dictionary (without decoding)
       of disk items.

    Args:
        dict (str): Information to be stripped and split into a dictionary
        delimiter (str): Text to split the information on

    Returns:
        stripped_dict (dict): Contains stripped and split information
    """
    stripped_dict = {}
    dict = dict.split("\n")
    print(dict)
    for entry in dict:
        temp = entry.lstrip().strip().split()
        print(temp)
        if temp[-1] == "disk":
            stripped_dict[temp[0]] = {}
            stripped_dict[temp[0]]["Size"] = temp[3]

    return stripped_dict


def strip_nics_dict(dict: str, nic_delimiter: str, line_delimiter: str) -> dict:
    """A helper method to strip whitespace and split a dictionary (without decoding)
       of NIC items.

    Args:
        dict (str): Information to be stripped and split into a dictionary
        nic_delimiter (str): Text to split the nics on
        line_delimiter (str): Text to split the lines on

    Returns:
        stripped_dict (dict): Contains stripped and split information
    """
    stripped_dict = {}
    dict = dict.split(nic_delimiter)
    dict.pop(0)
    for entry in dict:
        temp_dict = {}
        key = ""
        temp = entry.lstrip().strip().split("\n")
        temp.pop(0)
        for item in temp:
            temp_item = item.lstrip().strip().split(line_delimiter)
            temp_dict[temp_item[0]] = temp_item[1]
            if temp_item[0] == "logical name":
                key = temp_item[1]
        stripped_dict[key] = temp_dict

    return stripped_dict


def strip_nics_dict_coreos(
    dict: str, nic_delimiter: str, line_delimiter: str, child: pexpect.pty_spawn.spawn
) -> dict:
    """A helper method to strip whitespace and split a dictionary (without decoding)
       of NIC items.

    Args:
        dict (str): Information to be stripped and split into a dictionary
        nic_delimiter (str): Text to split the nics on
        line_delimiter (str): Text to split the lines on
        child (pexpect.pty_spawn.spawn): Pexpect spawn object from main script

    Returns:
        stripped_dict (dict): Contains stripped and split information
    """
    stripped_dict = {}
    dict = dict.split(nic_delimiter)
    curr_nic = ""
    for entry in dict:
        if line_delimiter in entry:
            split_entry = entry.split(": ")
            stripped_dict[split_entry[1]] = {}
            curr_nic = split_entry[1]
        else:
            split_entry = entry.split()
            if split_entry[0] == "link/ether":
                stripped_dict[curr_nic]["serial"] = split_entry[1]
                try:
                    child.sendline("sudo cat /sys/class/net/" + curr_nic + "/speed")
                    child.expect(".*\$ ", timeout=30)  # noqa: W605
                    capacity = child.after.strip().decode().split("\n")[1].strip()
                    stripped_dict[curr_nic]["capacity"] = capacity
                except Exception:
                    stripped_dict[curr_nic]["capacity"] = ""

    return stripped_dict


def strip_gpu_dict(dict: str, gpu_delimiter: str, line_delimiter: str) -> dict:
    """A helper method to strip whitespace and split a dictionary (without decoding)
       of GPU items.

    Args:
        dict (str): Information to be stripped and split into a dictionary
        nic_delimiter (str): Text to split the gpus on
        line_delimiter (str): Text to split the lines on

    Returns:
        stripped_dict (dict): Contains stripped and split information
    """
    stripped_dict = {}
    dict = dict.split(gpu_delimiter)
    dict.pop(0)
    for entry in dict:
        temp_dict = {}
        key = ""
        temp = entry.lstrip().strip().split("\n")
        temp.pop(0)
        for item in temp:
            temp_item = item.lstrip().strip().split(line_delimiter)
            temp_dict[temp_item[0]] = temp_item[1]
            if temp_item[0] == "product":
                key = temp_item[1]
        stripped_dict[key] = temp_dict

    return stripped_dict


def strip_brctl_showmacs_switch_dict(dict: str, delimiter: str) -> dict:
    """A helper method to strip whitespace and split a dictionary (without decoding)
       of switch items when the 'brctl showmacs br0' command is run.

    Args:
        dict (str): Information to be stripped and split into a dictionary
        delimiter (str): Text to split the information on

    Returns:
        stripped_dict (dict): Contains stripped and split information
    """
    interface_mac_count = {}
    stripped_dict = {}
    dict = dict.decode().split("\n")
    for entry in dict:
        temp = entry.lstrip().strip().split(delimiter)
        for item in range(len(temp)):
            temp_split = temp[item].split()
            if len(temp_split) >= 4 and temp_split[2] == "no":
                if temp_split[1] in stripped_dict:
                    print("Duplicate: " + temp_split[1])

                if temp_split[0] in interface_mac_count:
                    interface_mac_count[temp_split[0]] += 1
                else:
                    interface_mac_count[temp_split[0]] = 1
                stripped_dict[temp_split[1]] = (
                    temp_split[0]
                    + " "
                    + "{:02d}".format(interface_mac_count[temp_split[0]])
                )

    return stripped_dict


def strip_show_mac_address_table_switch_dict(dict: str, delimiter: str) -> dict:
    """A helper method to strip whitespace and split a dictionary (without decoding)
       of switch items when the 'show mac-address-table' command is run.

    Args:
        dict (str): Information to be stripped and split into a dictionary
        delimiter (str): Text to split the information on

    Returns:
        stripped_dict (dict): Contains stripped and split information
    """
    # NOTE: This is required because for some switches there seems to be the
    # possibility of multiple macs on single interfaces. My assumption is there
    # is an unmanaged switch or a breakout cable as the culprit.
    # TODO: Follow up on this line of thought to confirm.
    interface_mac_count = {}
    stripped_dict = {}
    dict = dict.decode().split("\n")
    for entry in dict:
        temp = entry.lstrip().strip().split(delimiter)
        if len(temp) == 5:
            temp[3] = temp[3].strip()
            if temp[3] in interface_mac_count:
                interface_mac_count[temp[3]] += 1
            else:
                interface_mac_count[temp[3]] = 1
            stripped_dict[temp[1]] = (
                temp[3] + " " + "{:02d}".format(interface_mac_count[temp[3]])
            )
    return stripped_dict


def strip_accelerator_dict(dict: str, delimiter: str) -> dict:
    """A helper method to strip whitespace and split a Processing accelerators
       dictionary (without decoding).

    Args:
        dict (str): Information to be stripped and split into a dictionary
        delimiter (str): Text to split the information on

    Returns:
        stripped_dict (dict): Contains stripped and split information
    """
    stripped_dict = {}
    print(dict)
    dict = dict.split("\n")
    for entry in dict:
        temp_dict = {}
        temp = entry.lstrip().strip().split(delimiter)
        if "Device" in temp and "accelerators:" in temp:
            device_index = temp.index("Device")
            manufacturer_index = temp.index("accelerators:") + 1
            manufacturer = ""
            manufacturer_length = device_index - manufacturer_index

            for i in range(manufacturer_length):
                manufacturer += temp[manufacturer_index + i]
                if i < (manufacturer_length - 1):
                    manufacturer += " "
            temp_dict["device"] = temp[device_index + 1]
            temp_dict["manufacturer"] = manufacturer
            stripped_dict[temp[0]] = temp_dict

    return stripped_dict
