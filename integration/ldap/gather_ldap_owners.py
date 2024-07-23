"""This script gathers all owners from our LDAP groups. Can be helpful for sending
communications, etc.
"""

import argparse
import sys

import compare_ldap_with_glpi as ldap
sys.path.append("../..")
from common.utils import print_final_help


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--ldap_config",
        metavar="ldap_config",
        help=(
            "path to LDAP config YAML/JSON file or name of env var that contains config"
            "data as a string, see integration/ldap/general_ldap_example.yaml. "
            "ex: -c ldap.yaml or -c ldap_config, if ldap_config is an env var that "
            "contains the config. (NOT -c $ldap_config)"
        ),
    )
    parser.add_argument(
        "-l",
        "--ldap-server",
        metavar="ldap_server",
        help="LDAP server to connect to (ex: ldaps://ldap.company.com)",
        required=True,
    )
    parser.add_argument(
        "-b",
        "--base_dn",
        metavar="base_dn",
        help="Base to use in the ldap query (ex: 'company')",
        required=True,
    )
    args = parser.parse_args()
    base_dn = args.base_dn

    # Process General Config
    group_map = ldap.parse_config_yaml(args)

    ldap_server = args.ldap_server

    group_map = ldap.gather_ldap_users(
        group_map, ldap_server, base_dn, ldap_attributes=["owner"]
    )

    owners = []
    for entry in group_map:
        owners.extend(group_map[entry]['users'])

    owners = list(set(owners))

    print("@redhat.com, ".join(owners) + "@redhat.com")
    print_final_help()


# Executes main if run as a script.
if __name__ == "__main__":
    main()
