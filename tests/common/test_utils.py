import sys

sys.path.append("..")

from pytest import mark

import common.utils as utils

@mark.skip("Not written")
def test_check_field():
    pass


@mark.skip("Not written")
def test_check_fields():
    pass


@mark.skip("Not written")
def test_check_field_without_range():
    pass


@mark.skip("Not written")
def test_check_and_post():
    pass


@mark.skip("Not written")
def test_check_and_post_processor():
    pass


@mark.skip("Not written")
def test_check_and_post_processor_item():
    pass


@mark.skip("Not written")
def test_check_and_post_network_port():
    pass


@mark.skip("Not written")
def test_check_and_post_network_port_network_port():
    pass


@mark.skip("Not written")
def test_check_and_post_device_memory_item():
    pass


@mark.skip("Not written")
def test_get_unspecified_device_memory():
    pass


@mark.skip("Not written")
def test_check_and_remove_unspecified_device_memory_item():
    pass


@mark.skip("Not written")
def test_print_final_help():
    pass


@mark.skip("Not written")
def test_get_reservations():
    pass


@mark.skip("Not written")
def test_get_switch_ports():
    pass


@mark.skip("Not written")
def test_error():
    pass

@mark.parametrize(
    "error_messages, expected_output",
    [
        ({}, "No errors detected!\n"),
        (
            {"127.0.0.1": "Connection Error", "127.0.0.2": "Timeout"},
            (
                "+-----------+------------------+\n"
                "| BMC IP    | Error Message    |\n"
                "+-----------+------------------+\n"
                "| 127.0.0.1 | Connection Error |\n"
                "| 127.0.0.2 | Timeout          |\n"
                "+-----------+------------------+"
            ),
        ),
    ],
)
def test_print_error_table(capsys, error_messages, expected_output):
    utils.print_error_table(error_messages)
    captured = capsys.readouterr()
    assert captured.out.strip() == expected_output.strip()
