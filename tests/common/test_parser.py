import sys

sys.path.append("../..")

from common.parser import argparser



def test_create_parser():
    parser = argparser()
    parser.test_parser

