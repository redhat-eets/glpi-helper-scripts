import sys

sys.path.append("..")
from common.sessionhandler import SessionHandler
from common.urlinitialization import UrlInitialization
from common.utils import (
    check_fields,
    check_field_without_range,
    print_final_help,
)
from prettytable import PrettyTable
from collections import defaultdict
from common.parser import argparser

# Suppress InsecureRequestWarning caused by REST access to Redfish without
# certificate validation.
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main() -> None:
    """Main Function"""
    # Get the command line arguments from the user
    parser = argparser()
    parser.parser.description = "Tag Unreservable Computers in GLPI"
    parser.parser.add_argument(
        "-n",
        "--name",
        required=True,
        help="Name of the tag to use. ex: 'Static Use Confirmation'",
    )
    args = parser.parser.parse_args()

    urls = UrlInitialization(args.ip)

    with SessionHandler(args.token, urls, args.no_verify) as session:
        # Check if plugin is installed
        plugin_list = check_field_without_range(session, urls.PLUGIN_URL)
        if all("Tag Management" not in plugin["name"] for plugin in plugin_list):
            raise Exception(
                (
                    "You need to install the 'Tag Management' plugin "
                    "(https://github.com/pluginsGLPI/tag) for this "
                    "script to work, exiting..."
                )
            )

        group_counts = defaultdict(lambda: defaultdict(dict))
        groups = check_fields(session, urls.GROUP_URL)
        for group in groups:
            unreservable_uri = (
                f"{urls.BASE_URL}search/Computer?criteria[0][field]=71&"
                "criteria[0][searchtype]=equals&"
                "criteria[0][value]={group['id']}&criteria[1][link]=AND&"
                "criteria[1][field]=81&criteria[1][searchtype]=contains&"
                "criteria[1][value]=NULL"
            )
            unreservable_computers = session.get(unreservable_uri)
            unreservable_count = unreservable_computers.json()["totalcount"]
            group_counts[group["completename"]][
                "unreservable_count"
            ] = unreservable_count

            tagged_uri = (
                f"{urls.BASE_URL}search/Computer?criteria[0][field]=71&"
                "criteria[0][searchtype]=equals&criteria[0][value]={group['id']}&"
                "criteria[1][link]=AND&criteria[1][field]=10500&"
                "criteria[1][searchtype]=equals&criteria[1][value]=1"
            )
            tagged_computers = session.get(tagged_uri)
            tagged_count = tagged_computers.json()["totalcount"]
            group_counts[group["completename"]]["tagged_count"] = tagged_count
        table = PrettyTable()
        table.field_names = ["Group", "Unreservable Count", "Tag Count"]
        for group in group_counts:
            table.add_row(
                [
                    group,
                    group_counts[group]["unreservable_count"],
                    group_counts[group]["tagged_count"],
                ]
            )
        print(table)
    print_final_help()


if __name__ == "__main__":
    main()
