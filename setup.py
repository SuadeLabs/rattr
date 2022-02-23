import os

from setuptools import setup, find_packages
from distutils.util import convert_path


here = os.path.abspath(os.path.dirname(__file__))

# Copy description from README.md
with open(os.path.join(here, "README.md"), "r") as f:
    DESCRIPTION = f.read()


# Copy requirements from requirements.txt
with open(os.path.join(here, "requirements.txt"), "r") as f:
    INSTALL_REQUIRES = [line.strip() for line in f.readlines()]


# Get version
version = {}
with open(convert_path("ratter/version.py")) as f:
    exec(f.read(), version)


setup(
    name="ratter",
    version=version.get("__version__"),
    author="Suade Labs",
    packages=find_packages(),
    description="Python 3.7 function analyser",
    long_description=DESCRIPTION,
    install_requires=INSTALL_REQUIRES,
    scripts=[
        "bin/ratter",
    ]
)
