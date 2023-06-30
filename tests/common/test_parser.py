import sys
import os
import subprocess

sys.path.append("..")

def test_create_parser():
    ip = "10.19.111.54"
    user_token = "qBIErMvrucSzVhwY92rC6bMq7Tj22N0nlCmhAxaO"
    os.environ["GLPI_INSTANCE"] = ip
    os.environ["GLPI_TOKEN"] = user_token
    output = subprocess.check_output(["./parser.py"], cwd="../../common")
    out = output.split()
    assert ip == out[0].decode("ascii")
    assert user_token == out[1].decode("ascii")
    os.environ["GLPI_INSTANCE"] = "1"
    os.environ["GLPI_TOKEN"] = "2"
    output = subprocess.check_output(
        ["./parser.py", "-i", ip, "-t", user_token], cwd="../../common"
    )
    out = output.split()
    assert ip == out[0].decode("ascii")
    assert user_token == out[1].decode("ascii")
