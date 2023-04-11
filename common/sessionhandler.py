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
from common.urlinitialization import UrlInitialization


log = logging.getLogger(__name__)


class SessionHandler:
    def __init__(
        self, token: str, urls: UrlInitialization, no_verify: bool = False
    ) -> None:
        """Initialize the session handler object

        Args:
            self:             self
            token (str):      the GLPI REST API token
            urls (UrlInitialization):   the GLPI URLs
            no_verify (bool): if present, this will not verify the SSL session
                              if it fails, allowing the script to proceed
        """
        log.debug("\nInitializing the REST session:")
        self.del_url = urls.KILL_URL
        self.session = requests.Session()
        self.session.headers.update({"Authorization": "user_token " + token})
        if no_verify:
            try:
                self.session_token = self.session.get(url=urls.INIT_URL)
            except requests.exceptions.SSLError:
                self.session.verify = False
                self.session_token = self.session.get(url=urls.INIT_URL)
        else:
            self.session_token = self.session.get(url=urls.INIT_URL)

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

    def __enter__(self) -> None:
        """Return the session

        Args:
            self: self
        """
        return self.session

    def __exit__(self, exception_type, exception, traceback) -> None:
        """Kill the REST session

        Args:
            self: self
        """
        log.debug("Killing session:")
        kill = self.session.get(url=self.del_url)
        log.debug(str(kill) + "\n")
