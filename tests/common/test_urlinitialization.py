import sys

sys.path.append("..")

from pytest import mark

from common.urlinitialization import UrlInitialization  # noqa: F401


@mark.skip("Not written")
def test_urlinitialization():
    pass
