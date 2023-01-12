import sys

sys.path.append("..")

from pytest import mark

import common.format_dicts as format_dicts


def test_strip_dict():
    list = [
        " space: single ".encode(),
        "    spaces: multiple    ".encode(),
        "\ttab: single\t".encode(),
        "\nnewline: single\n".encode(),
        "\t\ntab_new: newline\t\n".encode(),
        "\r\ncarriage_return: newline\r\n".encode(),
    ]
    stripped_dict = format_dicts.strip_dict(list, ": ")

    assert type(stripped_dict) is dict
    assert stripped_dict["space"] == "single"
    assert stripped_dict["spaces"] == "multiple"
    assert stripped_dict["tab"] == "single"
    assert stripped_dict["newline"] == "single"
    assert stripped_dict["tab_new"] == "newline"
    assert stripped_dict["carriage_return"] == "newline"


@mark.skip("Not written")
def test_decoded_dict():
    pass


@mark.skip("Not written")
def test_strip_network_dict():
    pass


@mark.skip("Not written")
def test_strip_ram_dict():
    pass


@mark.skip("Not written")
def test_ram_dict_coreos():
    pass


@mark.skip("Not written")
def test_strip_disks_dict():
    pass


@mark.skip("Not written")
def test_strip_disks_dict_coreos():
    pass


@mark.skip("Not written")
def test_strip_nics_dict():
    pass


@mark.skip("Not written")
def test_strip_nics_dict_coreos():
    pass


@mark.skip("Not written")
def test_strip_gpu_dict():
    pass


@mark.skip("Not written")
def test_strip_brctl_showmacs_switch_dict():
    pass


@mark.skip("Not written")
def test_strip_show_mac_address_table_switch_dict():
    pass


@mark.skip("Not written")
def test_strip_accelerator_dict():
    pass
