from __future__ import annotations

from pathlib import Path

from setuptools import find_packages, setup

HERE = Path(__file__).parent.resolve()
README = HERE / "README.md"
REQUIREMENTS = HERE / "requirements.txt"


_ = setup(
    name="rattr",
    use_scm_version={
        "write_to": "rattr/_version.py",
        "write_to_template": (
            'version = "{version}"  # this should be overwritten by setuptools_scm\n'
        ),
    },
    setup_requires=["setuptools_scm"],
    author="Suade Labs, Brandon Harris",
    author_email="brandon@saude.org, bpharris@pm.me",
    maintainer="Brandon Harris",
    maintainer_email="brandon@saude.org, bpharris@pm.me",
    packages=find_packages(),
    description="Rattr rats on your attrs.",
    long_description=README.read_text(),
    long_description_content_type="text/markdown",
    install_requires=[r.strip() for r in REQUIREMENTS.read_text().splitlines()],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "ruff==0.2.1",
        ],
    },
    entry_points={"console_scripts": ["rattr = rattr.__main__:entry_point"]},
    keywords="automation linting type-checking attributes rats",
    url="https://github.com/SuadeLabs/rattr",
    license="MIT",
    python_requires=">=3.9",
    classifiers=[
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Quality Assurance",
    ],
)
