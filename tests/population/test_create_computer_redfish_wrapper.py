import pytest
import population.create_glpi_computer_redfish_wrapper as redfish_wrapper
import argparse


@pytest.mark.parametrize(
    "args,expected_output",
    [
        (
            argparse.Namespace(
                general_config="/fake/file/path",
                token="faketoken",
                ip="127.0.0.1",
                no_dns=None,
                sku=None,
                switch_config=None,
                no_verify=None,
                put=None,
                experiment=None,
                overwrite=None,
                sunbird_username=None,
                sunbird_password=None,
                sunbird_url=None,
                sunbird_config=None,
                sku_for_dell=True
            ),
            [
                "./create_glpi_computer_redfish.py",
                "-g",
                "/fake/file/path",
                "-t",
                "faketoken",
                "--ipmi_ip",
                "127.0.0.1",
                "--ipmi_user",
                "user",
                "--ipmi_pass",
                "pass",
                "--public_ip",
                "127.0.0.2",
                "--lab",
                "Lab",
                "-i",
                "127.0.0.1",
            ],
        ),
        (
            argparse.Namespace(
                general_config="/fake/file/path",
                token="faketoken",
                ip="127.0.0.1",
                no_dns="test",
                sku=True,
                switch_config=None,
                no_verify=None,
                put=None,
                experiment=None,
                overwrite=None,
                sunbird_username="sb_user",
                sunbird_password=None,
                sunbird_url=None,
                sunbird_config=None,
                sku_for_dell=False
            ),
            [
                "./create_glpi_computer_redfish.py",
                "-g",
                "/fake/file/path",
                "-t",
                "faketoken",
                "--ipmi_ip",
                "127.0.0.1",
                "--ipmi_user",
                "user",
                "--ipmi_pass",
                "pass",
                "--public_ip",
                "127.0.0.2",
                "--lab",
                "Lab",
                "-i",
                "127.0.0.1",
                "-n",
                "test",
                "-s",
                "--sku_for_dell"
            ],
        ),
        (
            argparse.Namespace(
                general_config="/fake/file/path",
                token="faketoken",
                ip="127.0.0.1",
                no_dns="test",
                sku=True,
                switch_config=None,
                no_verify=None,
                put=None,
                experiment=None,
                overwrite=None,
                sunbird_username="sb_user",
                sunbird_password="sb_pass",
                sunbird_url="sb_url",
                sunbird_config=None,
                sku_for_dell=True
            ),
            [
                "./create_glpi_computer_redfish.py",
                "-g",
                "/fake/file/path",
                "-t",
                "faketoken",
                "--ipmi_ip",
                "127.0.0.1",
                "--ipmi_user",
                "user",
                "--ipmi_pass",
                "pass",
                "--public_ip",
                "127.0.0.2",
                "--lab",
                "Lab",
                "-i",
                "127.0.0.1",
                "-n",
                "test",
                "-s",
                "-U",
                "sb_user",
                "-P",
                "sb_pass",
                "-S",
                "sb_url",
            ],
        ),
    ],
)
def test_build_command(args, expected_output):
    split_line = ["127.0.0.1", "user", "pass", "127.0.0.2", "Lab"]
    command = redfish_wrapper.build_command(split_line, args)
    assert command == expected_output


@pytest.mark.parametrize(
    "error_messages, expected_output",
    [
        ({}, "No errors detected!\n"),
        (
            {"127.0.0.1": "Connection Error", "127.0.0.2": "Timeout"},
            (
                "+-----------+------------------+\n"
                "|   BMC IP  |  Error Message   |\n"
                "+-----------+------------------+\n"
                "| 127.0.0.1 | Connection Error |\n"
                "| 127.0.0.2 |     Timeout      |\n"
                "+-----------+------------------+"
            ),
        ),
    ],
)
def test_print_error_table(capsys, error_messages, expected_output):
    redfish_wrapper.print_error_table(error_messages)
    captured = capsys.readouterr()
    assert captured.out.strip() == expected_output.strip()
