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


def test_strip_ram_dict_coreos():
    input_dict = """MemTotal:       18723657 kB
        MemFree:         3719923 kB
        MemAvailable:    9587238 kB
        Buffers:          422764 kB
        Cached:          8523915 kB"""
    stripped_ram_dict = format_dicts.strip_ram_dict_coreos(input_dict)
    assert type(stripped_ram_dict) is dict
    assert stripped_ram_dict["MemTotal:"] == "18723657"
    assert stripped_ram_dict["MemFree:"] == "3719923"
    assert stripped_ram_dict["MemAvailable:"] == "9587238"
    assert stripped_ram_dict["Buffers:"] == "422764"
    assert stripped_ram_dict["Cached:"] == "8523915"


def test_strip_disks_dict():
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


def test_strip_disks_dict_coreos():
    # fake data
    input_string = """NAME MAJ:MIN RM SIZE RO TYPE MOUNTPOINT
    testa 8:0 0 123G 0 disk
    ├─testa1 8:1 0 512M 0 part /boot
    ├─testa2 8:2 0 99G 0 part
    └─testa3 8:3 0 4M 0 part
    testb 8:16 0 456G 0 disk"""

    stripped_disks_dict = format_dicts.strip_disks_dict_coreos(input_string, "\n")

    assert list(stripped_disks_dict.keys()) == ["testa", "testb"]
    assert stripped_disks_dict["testa"] == {"Size": "123G"}
    assert stripped_disks_dict["testb"] == {"Size": "456G"}


def test_strip_nics_dict():
    input_string = """*-network
            description: Ethernet interface
            product: Test Ethernet Controller (Test)
            vendor: Test Corporation
            physical id: 3
            bus info: pci@0000:00:00.0
            logical name: test0
            version: 01
            serial: 00:00:00:00:00:00
            size: TestGbit/s
    *-network
            description: Ethernet interface
            product: Test Ethernet Controller (Test)
            vendor: Test Corporation
            physical id: 5
            bus info: pci@0000:00:00.0
            logical name: test1
            version: 01
            serial: 00:00:00:00:00:00
            size: TestGbit/s
    """

    stripped_nics_dict = format_dicts.strip_nics_dict(input_string, "*", ": ")
    assert list(stripped_nics_dict.keys()) == ["test0", "test1"]
    assert stripped_nics_dict["test0"]["description"] == "Ethernet interface"
    assert stripped_nics_dict["test0"]["product"] == "Test Ethernet Controller (Test)"
    assert stripped_nics_dict["test0"]["vendor"] == "Test Corporation"
    assert stripped_nics_dict["test0"]["physical id"] == "3"
    assert stripped_nics_dict["test0"]["bus info"] == "pci@0000:00:00.0"
    assert stripped_nics_dict["test0"]["logical name"] == "test0"
    assert stripped_nics_dict["test0"]["version"] == "01"
    assert stripped_nics_dict["test0"]["serial"] == "00:00:00:00:00:00"
    assert stripped_nics_dict["test0"]["size"] == "TestGbit/s"

    assert stripped_nics_dict["test1"]["description"] == "Ethernet interface"
    assert stripped_nics_dict["test1"]["product"] == "Test Ethernet Controller (Test)"
    assert stripped_nics_dict["test1"]["vendor"] == "Test Corporation"
    assert stripped_nics_dict["test1"]["physical id"] == "5"
    assert stripped_nics_dict["test1"]["bus info"] == "pci@0000:00:00.0"
    assert stripped_nics_dict["test1"]["logical name"] == "test1"
    assert stripped_nics_dict["test1"]["version"] == "01"
    assert stripped_nics_dict["test1"]["serial"] == "00:00:00:00:00:00"
    assert stripped_nics_dict["test1"]["size"] == "TestGbit/s"


@mark.skip("Not written")
def test_strip_nics_dict_coreos():
    pass


def test_strip_gpu_dict():
    input_string = """*-display
       description: VGA compatible controller
       product: Graphics Controller
       vendor: Generic Corporation
       physical id: 2
       bus info: pci@0000:00:02.0
       logical name: /dev/fb0
       version: 01
       width: 64 bits
       clock: 33MHz
       capabilities: pciexpress msi pm vga_controller bus_master cap_list rom fb
       configuration: depth=32 driver=i915 latency=0 mode=1920x1080 resolution=1920,1080 visual=truecolor xres=1920 yres=1080
       resources: iomemory:600-5ff iomemory:400-3ff irq:135 memory:603c000000-603cffffff memory:4000000000-400fffffff ioport:3000(size=64) memory:c0000-dffff memory:4010000000-4016ffffff memory:4020000000-40ffffffff
    """  # noqa: E501
    gpu_delimiter = "*"
    line_delimiter = ": "
    result = format_dicts.strip_gpu_dict(input_string, gpu_delimiter, line_delimiter)
    print(result)
    assert list(result.keys()) == ["Graphics Controller"]
    assert result["Graphics Controller"]["description"] == "VGA compatible controller"
    assert result["Graphics Controller"]["product"] == "Graphics Controller"
    assert result["Graphics Controller"]["vendor"] == "Generic Corporation"
    assert result["Graphics Controller"]["physical id"] == "2"
    assert result["Graphics Controller"]["bus info"] == "pci@0000:00:02.0"
    assert result["Graphics Controller"]["logical name"] == "/dev/fb0"
    assert result["Graphics Controller"]["version"] == "01"
    assert result["Graphics Controller"]["width"] == "64 bits"
    assert result["Graphics Controller"]["clock"] == "33MHz"
    assert (
        result["Graphics Controller"]["capabilities"]
        == "pciexpress msi pm vga_controller bus_master cap_list rom fb"
    )
    assert (
        result["Graphics Controller"]["configuration"]
        == "depth=32 driver=i915 latency=0 mode=1920x1080 resolution=1920,1080 visual=truecolor xres=1920 yres=1080"  # noqa: E501
    )
    assert (
        result["Graphics Controller"]["resources"]
        == "iomemory:600-5ff iomemory:400-3ff irq:135 memory:603c000000-603cffffff memory:4000000000-400fffffff ioport:3000(size=64) memory:c0000-dffff memory:4010000000-4016ffffff memory:4020000000-40ffffffff"  # noqa: E501
    )


def test_strip_brctl_showmacs_switch_dict():
    input_string = b"""port no mac addr                is local?       ageing timer
    1     00:11:22:33:44:55       yes                 2.37
    2     00:66:77:88:99:00       no                  1.15
    3     00:AA:BB:CC:DD:EE       yes                 0.00
    """

    delimiter = "\n"

    result = format_dicts.strip_brctl_showmacs_switch_dict(input_string, delimiter)

    assert result["00:66:77:88:99:00"] == "2 01"


@mark.skip("Not written")
def test_strip_show_mac_address_table_switch_dict():
    pass


@mark.skip("Not working")
def test_strip_accelerator_dict():
    input_string = """
    0b:00.0 Device accelerators: NVIDIA Corporation GV100GL [Tesla V100 PCIe 16GB] (rev a1)
    0b:00.1 Device accelerators: NVIDIA Corporation GV100GL [Tesla V100 PCIe 16GB] (rev a1)
    """  # noqa: E501

    delimiter = " "

    expected_output = {
        "0b:00.0": {
            "device": "GV100GL",
            "manufacturer": "NVIDIA Corporation [Tesla V100 PCIe 16GB] (rev a1)",
        },
        "0b:00.1": {
            "device": "GV100GL",
            "manufacturer": "NVIDIA Corporation [Tesla V100 PCIe 16GB] (rev a1)",
        },
    }

    result = format_dicts.strip_accelerator_dict(input_string, delimiter)

    assert result == expected_output
