from __future__ import annotations

from pathlib import Path

from setuptools import find_packages, setup

HERE = Path(__file__).parent.resolve()
README = HERE / "README.md"
REQUIREMENTS = HERE / "requirements.txt"


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
    long_description=README.read_text(),
    long_description_content_type="text/markdown",
    install_requires=[r.strip() for r in REQUIREMENTS.read_text().splitlines()],
    extras_require={
        "dev": [
            "black==22.1.0",
            "click==8.0.2",
            "ruff==0.0.270",
            "isort==5.10.1",
            "pytest==7.0.1",
        ],
    },
    entry_points={"console_scripts": ["rattr = rattr.__main__:entry_point"]},
    keywords="automation linting type-checking attributes rats",
    url="https://github.com/SuadeLabs/rattr",
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
