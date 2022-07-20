import pathlib

from setuptools import find_packages, setup

HERE = pathlib.Path(__file__).parent.resolve()

# Copy description from README.md
with open(HERE / "README.md") as f:
    DESCRIPTION = f.read()

# Copy requirements from requirements.txt
with open(HERE / "requirements.txt") as f:
    INSTALL_REQUIRES = [line.strip() for line in f.readlines()]


setup(
    name="rattr",
    use_scm_version={
        "write_to": "rattr/_version.py",
        "write_to_template": (
            'version = "{version}"  # this should be overwritten by setuptools_scm\n'
        ),
    },
    setup_requires=["setuptools_scm"],
    author="Suade Labs",
    packages=find_packages(),
    description="Rattr rats on your attrs.",
    long_description=DESCRIPTION,
    long_description_content_type="text/markdown",
    install_requires=INSTALL_REQUIRES,
    extras_require={
        "dev": [
            "black==22.1.0",
            "click==8.0.2",
            "flake8-bugbear==22.1.11",
            "flake8==4.0.1",
            "flask==2.0.3",
            "isort==5.10.1",
            "pytest==7.0.1",
        ],
    },
    entry_points={"console_scripts": ["rattr = rattr.__main__:entry_point"]},
    keywords="automation linting type-checking attributes rats",
    url="https://github.com/SuadeLabs/ratter",
    license="MIT",
    python_requires=">=3.7",
    classifiers=[
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Quality Assurance",
    ],
)
