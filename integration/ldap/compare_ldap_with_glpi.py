import subprocess
import sys
import re
import os

import yaml
import requests

sys.path.append("../..")

# Suppress InsecureRequestWarning caused by REST access to Redfish without
# certificate validation.
import urllib3

from common.parser import argparser
from common.sessionhandler import SessionHandler
from common.urlinitialization import UrlInitialization
from common.utils import check_fields, print_final_help

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main():
    parser = argparser()
    parser.parser.add_argument(
        "-c",
        "--ldap_config",
        metavar="ldap_config",
        help=(
            "path to LDAP config YAML file or env var that contains config data "
            "as a string, see integration/ldap/general_ldap_example.yaml"
        ),
        required=True,
    )
    parser.parser.add_argument(
        "-l",
        "--ldap-server",
        metavar="ldap_server",
        help="LDAP server to connect to (ex: ldaps://ldap.company.com)",
        required=True,
    )
    parser.parser.add_argument(
        "-b",
        "--base_dn",
        metavar="base_dn",
        help="Base to use in the ldap query (ex: 'company')",
        required=True,
    )
    args = parser.parser.parse_args()
    ip = args.ip
    user_token = args.token
    no_verify = args.no_verify
    base_dn = args.base_dn

    # Process General Config
    if os.path.isfile(args.ldap_config):
        # Process YAML file
        with open(args.ldap_config, "r") as config_path:
            group_map = yaml.safe_load(config_path)
    else:
        # Process YAML env var
        yaml_content = os.getenv(args.ldap_config, "{}")
        group_map = yaml.safe_load(yaml_content)

    ldap_server = args.ldap_server

    group_map = gather_ldap_users(group_map, ldap_server, base_dn)

    urls = UrlInitialization(ip)
    with SessionHandler(user_token, urls, no_verify) as session:
        sync_ldap_with_glpi(session, urls, group_map)

    print_final_help()


def gather_ldap_users(group_map: dict, ldap_server: str, base_dn: str) -> dict:
    """Use ldapsearch to get all users from the specified LDAP groups

    Args:
        group_map (dict): User-defined dictionary w/ ldap groups to search
        ldap_server (str): Specifies the ldap server to search
        base_dn (str): Base to use in the ldap query (ex: 'company')

    Returns:
        dict: Group map with users for each group
    """
    ldap_search_filter = "(|"
    for group in group_map:
        for ldap_group in group_map[group]["ldap"]:
            ldap_search_filter += f"(cn={ldap_group})"
    ldap_search_filter += ")"
    ldap_username = ""
    ldap_password = ""
    ldap_search_base = f"ou=adhoc,ou=managedGroups,dc={base_dn},dc=com"
    ldap_attributes = ["owner", "uniqueMember"]

    cmd = [
        "ldapsearch",
        "-LLL",
        "-H",
        ldap_server,
        "-x",
        "-D",
        ldap_username,
        "-w",
        ldap_password,
        "-b",
        ldap_search_base,
        ldap_search_filter,
    ] + ldap_attributes

    result = subprocess.check_output(cmd).decode("utf-8")

    if result:
        group_map = parse_ldap(result, group_map)
    else:
        print("No results found.")

    return group_map


def parse_ldap(result: str, group_map: dict) -> dict:
    """Organizes LDAP response and modifies group map accordingly

    Args:
        result (str): Response from ldapsearch
        group_map (dict): User-defined dictionary w/ ldap groups to search
    Returns:
        dict: Group map with users for each group
    """
    groups = result.strip().split("\n\n")

    # Regular expression patterns for matching lines
    dn_pattern = re.compile(r"^dn:\s*cn=([^,]+)", re.MULTILINE)
    owner_pattern = re.compile(r"^owner:\s*uid=([^,]+)", re.MULTILINE)
    member_pattern = re.compile(r"^uniqueMember:\s*uid=([^,]+)", re.MULTILINE)

    for group in groups:
        dn_match = dn_pattern.search(group)
        if dn_match:
            # Extract the distinguished name
            dn = dn_match.group(1)
            for mapping_name, mapping_info in group_map.items():
                for ldap_group in mapping_info["ldap"]:
                    if ldap_group == dn:
                        # Find all owners and members for this group
                        owners = owner_pattern.findall(group)
                        members = member_pattern.findall(group)
                        # Store the results in the group_map
                        if "users" not in group_map[mapping_name]:
                            group_map[mapping_name]["users"] = []
                        group_map[mapping_name]["users"] += list(set(owners + members))
    return group_map


def sync_ldap_with_glpi(
    session: requests.sessions.Session, urls: UrlInitialization, group_map: dict
) -> None:
    """Sync GLPI groups with LDAP groups

    Args:
        session (requests.sessions.Session): The requests session object
        urls (UrlInitialization): the URL object
        group_map (dict): User-defined dictionary w/ ldap groups to search
    """
    all_users = check_fields(session, urls.USER_URL)
    group_response_list = check_fields(session, urls.GROUP_URL)
    for group in group_response_list:
        users_in_group = get_users_in_group(session, urls, str(group["id"]))

        if group["completename"] in group_map:
            # add group names to comments
            update_group_comments(session, urls.GROUP_URL, group, group_map)

            add_missing_users_to_group(
                session, urls.BASE_URL, group, users_in_group, group_map, all_users
            )


def get_users_in_group(
    session: requests.sessions.Session, urls: UrlInitialization, group_id: str
) -> list:
    """Get all GLPI users in a specific GLPI group

    Args:
        session (requests.sessions.Session): The requests session object
        urls (UrlInitialization): The URL object
        group_id (str): The ID of the GLPI group

    Returns:
        list: Contains all GLPI users in the specified group
    """
    users_in_group = []
    users_response_list = check_fields(
        session, f"{urls.GROUP_URL}{group_id}/Group_User"
    )
    for user in users_response_list:
        user_info = session.get(f"{urls.USER_URL}{str(user['users_id'])}")
        users_in_group.append(user_info.json()["name"])
    return users_in_group


def update_group_comments(
    session: requests.sessions.Session, group_url: str, group: dict, group_map: dict
) -> None:
    """Add LDAP group to the comments field of the GLPI group

    Args:
        session (requests.sessions.Session): The requests session object
        group_url (str): GLPI API endpoint for groups
        group (dict): GLPI group and its related fields that will be modified
        group_map (dict): User-defined dictionary w/ ldap groups to search
    """
    comment = ""
    for ldap_group in group_map[group['completename']]['ldap']:
        if ldap_group not in group["comment"]:
            comment += f"Rover: {ldap_group}\n"
            print(f"Adding '{ldap_group}' to group comment")
    if group["comment"] is not None:
        # Append pre-existing comment
        comment += f"{group['comment']}"
    comment_post = {"comment": comment}
    session.put(
        group_url + str(group["id"]),
        json={"input": comment_post},
    )


def add_missing_users_to_group(
    session: requests.sessions.Session,
    base_url: str,
    group: dict,
    users_in_group: list,
    group_map: dict,
    all_users: list,
) -> None:
    """Add users to GLPI groups if they aren't already associated

    Args:
        session (requests.sessions.Session): The requests session object
        base_url (str): GLPI API base endpoint
        group (dict): GLPI group and its related fields that will be modified
        users_in_group (list): Users already in the GLPI group
        group_map (dict): User-defined dictionary w/ ldap groups to search
        all_users (list): All GLPI users
    """
    if "users" in group_map[group["completename"]]:
        users_to_add = list(
            set(group_map[group["completename"]]["users"]) - set(users_in_group)
        )
        for user in all_users:
            if user["name"] in users_to_add:
                print(
                    f"Adding {user['name']} to {group['completename']}: {group['id']}"
                )
                glpi_post = {
                    "groups_id": group["id"],
                    "users_id": user["id"],
                }
                session.post(base_url + "Group_User", json={"input": glpi_post})


# Executes main if run as a script.
if __name__ == "__main__":
    main()
