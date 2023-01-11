"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: switches.py                                                     |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: Class to handle switch information                              |
|                                                                              |
|------------------------------------------------------------------------------|
"""

import yaml


class Switches:
    def __init__(self, switch: str = None) -> None:
        """Initialize the switches object
        Args:
            self:         self
            switch (str): path to YAML file containing switch information
        """
        self.TERMINAL_PROMPT = ".*[#\$>]"  # noqa: W605
        # MAC tables commands
        self.BRCTL_SHOWMACS_SWITCH_COMMAND = "brctl showmacs br0"  # Cumulus
        self.SHOW_MAC_ADDRESS_TABLE_SWITCH_COMMAND = "show mac-address-table"  # Dell
        # Serial number/service tag commands
        self.DECODE_SYSEEPROM_SWITCH_COMMAND = "sudo decode-syseeprom -e"  # Cumulus
        self.SHOW_SYSTEM_SERICE_TAG_SWITCH_COMMAND = (
            'show system stack-unit 1 | grep "Service Tag"'  # Dell
        )
        # Interface commands
        self.NETSHOW_INTERFACE_SWITCH_COMMAND = "netshow interface"  # Cumulus
        self.SHOW_INTERFACES_STATUS_SWITCH_COMMAND = "show interfaces status"  # Dell
        if switch:
            with open(switch, "r") as switch_path:
                self.switch_map = yaml.safe_load(switch_path)
        else:
            self.switch_map = {}
