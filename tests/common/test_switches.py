import sys

sys.path.append("..")

from pytest import mark

from common.switches import Switches  # noqa: F401


@mark.skip("Not written")
def test_switches():
    pass
