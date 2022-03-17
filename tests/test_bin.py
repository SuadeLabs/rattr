import subprocess


def test_bin():
    subprocess.check_call(["rattr", "--version"])
