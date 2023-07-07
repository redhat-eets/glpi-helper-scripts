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


def test_decoded_dict():
    string = """
             space: single 
                spaces: multiple   
            \ttab: single\t
            \nnewline: single\n
            \t\ntab_new: newline\t\n
            \r\ncarriage_return: newline\r\n
            """
    stripped_decoded_dict = format_dicts.strip_decoded_dict(string, ":")

    assert type(stripped_decoded_dict) is dict
    assert stripped_decoded_dict["space"] == "single"
    assert stripped_decoded_dict["spaces"] == "multiple"
    assert stripped_decoded_dict["tab"] == "single"
    assert stripped_decoded_dict["newline"] == "single"
    assert stripped_decoded_dict["tab_new"] == "newline"
    assert stripped_decoded_dict["carriage_return"] == "newline"


def test_strip_network_dict():
    string = """
            space: single space\n single space

            spaces: multiple   spaces \n   multiple   spaces

        \ttab: single tab\t

        \nnewline: single\nsingle

        \t\ntab_new: newline\t\nnewline

        \r\ncarriage_return: newline\r\n new line

        ovirtmgmt: ovirtmgmt
        """
    stripped_network_dict = format_dicts.strip_network_dict(string, ": ")

    assert type(stripped_network_dict) is dict
    assert stripped_network_dict["space"] == [["single", "space"], ["single", "space"]]
    assert stripped_network_dict["spaces"] == [
        ["multiple", "spaces"],
        ["multiple", "spaces"],
    ]
    assert stripped_network_dict["tab"] == [["single", "tab"]]
    assert stripped_network_dict["newline"] == [["single"], ["single"]]
    assert stripped_network_dict["tab_new"] == [["newline"], ["newline"]]
    assert stripped_network_dict["carriage_return"] == [["newline"], ["new", "line"]]
    assert "ovirtmgmt" not in stripped_network_dict


@mark.skip("Not written")
def test_strip_network_coreos_dict():
    pass


def test_strip_ram_dict():
    string = """Should\nnot\nbe\nincluded\n

        space
        space
        single space: single space

            spaces
            spaces 
            multiple   spaces: multiple   spaces

        \ttab
        \ttab
        single tab: single tab\t

        \nnewline
        \nnewline
        single newline: single newline

        \t\ntab_new
        \t\ntab_new
        newline\t: tab_new

        \r\ncarriage_return
        \r\ncarriage_return
        newline: \rcarriage_return

        one line
        one line: should be empty
        """
    stripped_ram_dict = format_dicts.strip_ram_dict(string, ": ")
    assert type(stripped_ram_dict) is dict
    assert stripped_ram_dict["space"] == {"single space": "single space"}
    assert stripped_ram_dict["spaces"] == {"multiple   spaces": "multiple   spaces"}
    assert stripped_ram_dict["tab"] == {"single tab": "single tab"}
    assert stripped_ram_dict["newline"] == {"single newline": "single newline"}
    assert stripped_ram_dict["tab_new"] == {"newline\t": "tab_new"}
    assert stripped_ram_dict["carriage_return"] == {"newline": "\rcarriage_return"}
    assert stripped_ram_dict["one line"] == {}
    assert "Should" not in stripped_ram_dict
    assert "not" not in stripped_ram_dict
    assert "be" not in stripped_ram_dict
    assert "included" not in stripped_ram_dict


@mark.skip("Not written")
def test_ram_dict_coreos():
    pass


def test_strip_disks_dict():
    # model first
    # not model first
    string = """ Model: Model Name          
            single space: single space
                multiple     spaces: multiple     spaces     
            \t single tab: single tab
            \r carriage return: carriage return
            """
    stripped_disks_dict = format_dicts.strip_disks_dict(string, ": ")
    assert type(stripped_disks_dict) is dict
    assert list(stripped_disks_dict.keys()) == ["0: Model Name"]
    assert stripped_disks_dict["0: Model Name"]["single space"] == "single space"
    assert (
        stripped_disks_dict["0: Model Name"]["multiple     spaces"]
        == "multiple     spaces"
    )
    assert stripped_disks_dict["0: Model Name"]["single tab"] == "single tab"
    assert stripped_disks_dict["0: Model Name"]["carriage return"] == "carriage return"


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
