"""
|------------------------------------------------------------------------------|
|                                                                              |
|    Filename: sessionhandler.py                                               |
|     Authors: Daniel Kostecki                                                 |
|              Adhitya Logan                                                   |
| Description: Class to create and delete GLPI API sessions gracefully         |
|                                                                              |
|------------------------------------------------------------------------------|
"""

import logging
import requests

log = logging.getLogger(__name__)


class SessionHandler:
    def __init__(
        self, token: str, init_url: str, del_url: str, no_verify: bool = False
    ) -> None:
        """Initialize the session handler object

        Args:
            self:             self
            token (str):      the GLPI REST API token
            init_url (str):   the initialization GLPI URL
            del_url (str):    the deletion GLPI URL
            no_verify (bool): if present, this will not verify the SSL session
                              if it fails, allowing the script to proceed
        """
        log.debug("\nInitializing the REST session:")
        self.del_url = del_url
        self.session = requests.Session()
        self.session.headers.update({"Authorization": "user_token " + token})
        if no_verify:
            try:
                self.session_token = self.session.get(url=init_url)
            except requests.exceptions.SSLError:
                self.session.verify = False
                self.session_token = self.session.get(url=init_url)
        else:
            self.session_token = self.session.get(url=init_url)

        if "session_token" not in self.session_token.json():
            print(
                "An error occurred when initializing the REST session:",
                self.session_token.json(),
                "exiting...",
                sep="\n",
            )
            exit()
        self.session.headers.update(
            {"Session-Token": self.session_token.json()["session_token"]}
        )
        log.debug(str(self.session_token) + "\n")

    def __del__(self) -> None:
        """Kill the REST session

        Args:
            self: self
        """
        log.debug("Killing session:")
        kill = self.session.get(url=self.del_url)
        log.debug(str(kill) + "\n")
