"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: urlinitialization.py                                            |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: Class to store GLPI API endpoints                               |
|                                                                              |
|------------------------------------------------------------------------------|
"""

import urllib.parse


class UrlInitialization:
    def __init__(self, ip: str) -> None:
        """Initialize the URL Initialization object

        Args:
            self:        self
            ip (str):    the GLPI IP address or hostname
        """
        # GLPI API URLS
        self.HOME_URL = validate_url(ip)

        # Session
        self.BASE_URL = self.HOME_URL + "/apirest.php/"
        self.INIT_URL = self.BASE_URL + "initSession"
        self.KILL_URL = self.BASE_URL + "killSession"

        # Computer
        self.COMPUTER_URL = self.BASE_URL + "Computer/"
        self.COMPUTER_TYPE_URL = self.BASE_URL + "ComputerType/"
        self.MANUFACTURER_URL = self.BASE_URL + "Manufacturer/"
        self.COMPUTER_MODEL_URL = self.BASE_URL + "ComputerModel/"

        # Reservation
        self.RESERVATION_URL = self.BASE_URL + "Reservation/"
        self.RESERVATION_ITEM_URL = self.BASE_URL + "ReservationItem/"

        # CPU
        self.CPU_URL = self.BASE_URL + "DeviceProcessor/"
        self.CPU_ITEM_URL = self.BASE_URL + "Item_DeviceProcessor/"

        # OS
        self.OPERATING_SYSTEM_URL = self.BASE_URL + "OperatingSystem/"
        self.OPERATING_SYSTEM_VERSION_URL = self.BASE_URL + "OperatingSystemVersion/"
        self.OPERATING_SYSTEM_ARCHITECTURE_URL = (
            self.BASE_URL + "OperatingSystemArchitecture/"
        )
        self.OPERATING_SYSTEM_KERNEL_VERSION_URL = (
            self.BASE_URL + "OperatingSystemKernelVersion/"
        )
        self.OPERATING_SYSTEM_ITEM_URL = self.BASE_URL + "Item_OperatingSystem/"

        # Memory
        self.DEVICE_MEMORY_URL = self.BASE_URL + "DeviceMemory/"
        self.DEVICE_MEMORY_TYPE_URL = self.BASE_URL + "DeviceMemoryType/"
        self.DEVICE_MEMORY_ITEM_URL = self.BASE_URL + "Item_DeviceMemory/"

        # Network
        self.NETWORK_PORT_URL = self.BASE_URL + "NetworkPort/"
        self.NETWORK_PORT_ETHERNET_URL = self.BASE_URL + "NetworkPortEthernet/"
        self.NETWORK_PORT_NETWORK_PORT_URL = self.BASE_URL + "NetworkPort_NetworkPort/"

        # NIC
        self.DEVICE_NETWORK_CARD_URL = self.BASE_URL + "DeviceNetworkCard/"
        self.DEVICE_NETWORK_CARD_ITEM_URL = self.BASE_URL + "Item_DeviceNetworkCard/"
        self.DEVICE_NETWORK_CARD_MODEL_URL = self.BASE_URL + "DeviceNetworkCardModel/"
        self.NETWORK_EQUIPMENT_URL = self.BASE_URL + "NetworkEquipment/"
        self.NETWORK_EQUIPMENT_TYPE_URL = self.BASE_URL + "NetworkEquipmentType/"

        # GPU
        self.DEVICE_GRAPHICS_CARD_URL = self.BASE_URL + "DeviceGraphicCard/"
        self.DEVICE_GRAPHICS_CARD_MODEL_URL = self.BASE_URL + "DeviceGraphicCardModel/"
        self.DEVICE_GRAPHICS_CARD_ITEM_URL = self.BASE_URL + "Item_DeviceGraphicCard/"

        # Disk
        self.DISK_ITEM_URL = self.BASE_URL + "Item_Disk/"
        self.LOCATION_URL = self.BASE_URL + "Location/"

        # MISC
        self.USER_URL = self.BASE_URL + "USER/"
        self.LOCATION_URL = self.BASE_URL + "Location/"
        self.BMC_URL = self.BASE_URL + "PluginFieldsComputerbmcaddres/"

        # Redfish API URLS (Supermicro rev 1.0a)
        self.REDFISH_SYSTEM_GENERIC = "/redfish/v1/Systems"

        # Computer link
        self.COMPUTER_LINK_URL = self.HOME_URL + "/front/computer.form.php?id="


def validate_url(ip: str) -> str:
    """Validate and format a user-provided URL

    Args:
        ip (str): a user-provided URL

    Returns:
        p.geturl() (str): the validated/formatted URL
    """

    # Partially referenced from: https://stackoverflow.com/a/21659195

    p = urllib.parse.urlparse(ip, "http")
    netloc = p.netloc or p.path
    path = p.path if p.netloc else ""
    p = urllib.parse.ParseResult("https", netloc, path, *p[3:])

    # The expected behavior is this failing on improper format of IP
    try:
        urllib.request.urlopen(p.geturl(), timeout=30)
    except Exception:
        p = urllib.parse.ParseResult("http", netloc, path, *p[3:])
        urllib.request.urlopen(p.geturl(), timeout=30)

    return p.geturl()
