import sys

sys.path.append("..")

from pytest import mark

from common.sessionhandler import SessionHandler  # noqa: F401


@mark.skip("Not written")
def test_sessionhandler():
    pass
