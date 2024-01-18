import sys
import os

sys.path.append("../..")

from common.parser import argparser


def test_create_parser():
    ip = "127.0.0.1"
    user_token = "1"
    os.environ["GLPI_INSTANCE"] = ip
    os.environ["GLPI_TOKEN"] = user_token
    parser = argparser()
    args = parser.parser.parse_args([])
    assert args.ip == ip
    assert args.token == user_token
    os.environ["GLPI_INSTANCE"] = "1"
    os.environ["GLPI_TOKEN"] = "2"
    parser = argparser()
    args = parser.parser.parse_args(["-i", ip, "-t", user_token])
    assert args.ip == ip
    assert args.token == user_token
