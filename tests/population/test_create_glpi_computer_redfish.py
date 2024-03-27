import socket

import pytest
import population.create_glpi_computer_redfish as create_redfish


@pytest.mark.parametrize(
    "public_ip, sku, system_json, expected_result, expected_print",
    [
        # DNS works
        (
            "127.0.0.1",
            "ABC123",
            {"Manufacturer": "Dell", "SKU": "XYZ456"},
            "hostname.example.com",
            None,
        ),
        # DNS doesn't work, use SKU
        (
            "127.0.0.1",
            "ABC123",
            {"Manufacturer": "Dell", "SKU": "XYZ456"},
            "XYZ456",
            "DNS not working, using SKU as name instead",
        ),
        # DNS doesn't work and SKU not present, use Serial Number
        (
            "127.0.0.1",
            "",
            {"Manufacturer": "Dell", "SerialNumber": "SN123"},
            "SN123",
            "DNS not working, using SerialNumber as name instead",
        ),
    ],
)
def test_get_hostname(
    public_ip, sku, system_json, expected_result, expected_print, mocker, capsys
):
    mock_socket = mocker.patch("socket.gethostbyaddr")
    mock_socket.return_value = (
        ("hostname.example.com", [], [])
        if expected_result == "hostname.example.com"
        else None
    )
    mock_socket.side_effect = (
        socket.herror("DNS resolution failed")
        if expected_result != "hostname.example.com"
        else None
    )

    hostname = create_redfish.get_hostname(public_ip, sku, system_json)

    mock_socket.assert_called_once_with(public_ip)
    assert hostname == expected_result
    if expected_print:
        assert capsys.readouterr().out.strip() == expected_print


def test_get_processor(mocker):
    mock_cpu = mocker.patch("redfish.rest.v1.HttpClient")

    create_redfish.REDFISH_PROCESSOR_URI = "test"  # set global
    response = {
        "@odata.context": "/redfish/v1/$metadata#ProcessorCollection.ProcessorCollection", # noqa: E501
        "@odata.id": "/redfish/v1/Systems/System.Embedded.1/Processors",
        "@odata.type": "#ProcessorCollection.ProcessorCollection",
        "Description": "Collection of Processors for this System",
        "Members": [
            {
                "@odata.id": "/redfish/v1/Systems/System.Embedded.1/Processors/CPU.Socket.2" # noqa: E501
            },
            {
                "@odata.id": "/redfish/v1/Systems/System.Embedded.1/Processors/CPU.Socket.1" # noqa: E501
            },
        ],
        "Members@odata.count": 2,
        "Name": "ProcessorsCollection",
    }

    mock_cpu.get.side_effect = [
        mocker.MagicMock(status=200, dict=response),
        mocker.MagicMock(
            status=200,
            dict={
                "ProcessorType": "CPU",
                "Socket": "CPU.Socket.1",
                "Status": {"Health": "OK", "State": "Enabled"},
                "TotalCores": 26,
                "TotalEnabledCores": 26,
                "TotalThreads": 52,
            },
        ),
        mocker.MagicMock(
            status=200,
            dict={
                "ProcessorType": "CPU",
                "Socket": "CPU.Socket.2",
                "Status": {"Health": "OK", "State": "Enabled"},
                "TotalCores": 26,
                "TotalEnabledCores": 26,
                "TotalThreads": 52,
            },
        ),
    ]

    cpu_list = create_redfish.get_processor(mock_cpu)
    assert cpu_list == [
        {
            "ProcessorType": "CPU",
            "Socket": "CPU.Socket.1",
            "Status": {"Health": "OK", "State": "Enabled"},
            "TotalCores": 26,
            "TotalEnabledCores": 26,
            "TotalThreads": 52,
        },
        {
            "ProcessorType": "CPU",
            "Socket": "CPU.Socket.2",
            "Status": {"Health": "OK", "State": "Enabled"},
            "TotalCores": 26,
            "TotalEnabledCores": 26,
            "TotalThreads": 52,
        },
    ]


def test_get_memory(mocker):
    mock_ram = mocker.patch("redfish.rest.v1.HttpClient")

    create_redfish.REDFISH_MEMORY_URI = "test"  # set global
    response = {
        "@odata.context": "/redfish/v1/$metadata#MemoryCollection.MemoryCollection",
        "@odata.id": "/redfish/v1/Systems/System.Embedded.1/Memory",
        "@odata.type": "#MemoryCollection.MemoryCollection",
        "Description": "Collection of memory devices for this system",
        "Members": [
            {
                "@odata.id": "/redfish/v1/Systems/System.Embedded.1/Memory/DIMM.Socket.A1" # noqa: E501
            },
            {
                "@odata.id": "/redfish/v1/Systems/System.Embedded.1/Memory/DIMM.Socket.A6" # noqa: E501
            },
        ],
        "Members@odata.count": 2,
        "Name": "Memory Devices Collection",
    }

    mock_ram.get.side_effect = [
        mocker.MagicMock(status=200, dict=response),
        mocker.MagicMock(
            status=200,
            dict={
                "AllowedSpeedsMHz": [2666],
                "AllowedSpeedsMHz@odata.count": 1,
                "BaseModuleType": "RDIMM",
                "BusWidthBits": 72,
                "CacheSizeMiB": 0,
                "CapacityMiB": 8192,
                "DataWidthBits": 64,
                "Description": "DIMM A1",
                "DeviceLocator": "DIMM A1",
                "Enabled": True,
            },
        ),
        mocker.MagicMock(
            status=200,
            dict={
                "AllowedSpeedsMHz": [2666],
                "AllowedSpeedsMHz@odata.count": 1,
                "BaseModuleType": "RDIMM",
                "BusWidthBits": 72,
                "CacheSizeMiB": 0,
                "CapacityMiB": 8192,
                "DataWidthBits": 64,
                "Description": "DIMM A6",
                "DeviceLocator": "DIMM A6",
                "Enabled": True,
            },
        ),
    ]

    ram_list = create_redfish.get_processor(mock_ram)
    assert ram_list == [
        {
            "AllowedSpeedsMHz": [2666],
            "AllowedSpeedsMHz@odata.count": 1,
            "BaseModuleType": "RDIMM",
            "BusWidthBits": 72,
            "CacheSizeMiB": 0,
            "CapacityMiB": 8192,
            "DataWidthBits": 64,
            "Description": "DIMM A1",
            "DeviceLocator": "DIMM A1",
            "Enabled": True,
        },
        {
            "AllowedSpeedsMHz": [2666],
            "AllowedSpeedsMHz@odata.count": 1,
            "BaseModuleType": "RDIMM",
            "BusWidthBits": 72,
            "CacheSizeMiB": 0,
            "CapacityMiB": 8192,
            "DataWidthBits": 64,
            "Description": "DIMM A6",
            "DeviceLocator": "DIMM A6",
            "Enabled": True,
        },
    ]
