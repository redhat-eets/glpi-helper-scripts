import socket

import pytest
import population.create_glpi_computer_redfish as redfish


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

    hostname = redfish.get_hostname(public_ip, sku, system_json)

    mock_socket.assert_called_once_with(public_ip)
    assert hostname == expected_result
    if expected_print:
        assert capsys.readouterr().out.strip() == expected_print
