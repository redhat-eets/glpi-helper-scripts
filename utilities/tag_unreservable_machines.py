import sys

sys.path.append("..")
from common.sessionhandler import SessionHandler
from common.urlinitialization import UrlInitialization
from common.utils import (
    check_fields,
    check_field_without_range,
    print_final_help,
    check_and_post,
    check_computer_reservable,
)
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

        # Create Tag if it doesn't exist
        tag_search_criteria = {
            "name": args.name,
        }
        tag_additional_criteria = {
            "color": "#e01b24",
            "comment": (
                "Used to tag static/unreservable assets periodically, "
                "to ensure that they are still used."
            ),
            "type_menu": ["Computer"],
        }
        tag_id = check_and_post(
            session,
            urls.TAG_URL,
            tag_search_criteria,
            tag_additional_criteria,
        )

        # Tag Unreservable Computers with specified tag
        computers = check_fields(session, urls.COMPUTER_URL)
        for computer in computers:
            computer_reservable = False
            for link in computer["links"]:
                if link["rel"] == "ReservationItem":
                    computer_reservable = check_computer_reservable(session, link)
                    if not computer_reservable:
                        tag_item_search_criteria = {
                            "items_id": computer["id"],
                            "itemtype": "Computer",
                            "plugin_tag_tags_id": tag_id,
                        }
                        check_and_post(
                            session,
                            urls.TAG_ITEM_URL,
                            tag_item_search_criteria,
                        )
    print_final_help()


if __name__ == "__main__":
    main()
