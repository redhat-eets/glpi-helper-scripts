#!/usr/bin/env python3

import argparse
from os import getenv


class argparser:
    def __init__(self) -> None:
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument(
            "-i",
            "--ip",
            metavar="ip",
            type=str,
            default=getenv("GLPI_INSTANCE"),
            required=not getenv("GLPI_INSTANCE"),
            help='the IP of the GLPI instance (example: "127.0.0.1")',
        )
        self.parser.add_argument(
            "-t",
            "--token",
            metavar="user_token",
            type=str,
            default=getenv("GLPI_TOKEN"),
            required=not getenv("GLPI_TOKEN"),
            help="the user token string for authentication with GLPI."
            + "This is the API token generated through GLPI under remote"
            + "access keys.",
        )
        self.parser.add_argument(
            "-v",
            "--no_verify",
            action="store_true",
            help="Use this flag if you want to "
            + "not verify the SSL session if it fails",
        )
