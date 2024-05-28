from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from rattr.cli.toml import _load_from_file

if TYPE_CHECKING:
    from typing import Any


def find_data_file(name: str) -> Path:
    here = Path(__file__).resolve().parent

    data_file = here / "data" / name
    assert data_file.is_file()

    return data_file


@pytest.fixture
def illegal_field_name() -> str:
    return "illegal-field"


@pytest.fixture
def required_sys_args() -> list[str]:
    return ["my/rattr/target.py"]


@pytest.fixture
def required_sys_args_rattr_target() -> str:
    if sys.platform == "win32":
        return "my\\rattr\\target.py"
    return "my/rattr/target.py"


@pytest.fixture
def toml_well_formed_path() -> Path:
    return find_data_file("well_formed.toml")


@pytest.fixture
def toml_well_formed(toml_well_formed_path) -> dict[str, Any]:
    return _load_from_file(toml_well_formed_path).get("tool", {}).get("rattr", {})


@pytest.fixture
def toml_with_illegal_field(illegal_field_name, toml_well_formed) -> dict[str, Any]:
    return {**toml_well_formed, **{illegal_field_name: "any-old-value"}}


@pytest.fixture
def toml_override_path() -> Path:
    return find_data_file("override.toml")


@pytest.fixture
def toml_override(toml_override_path) -> dict[str, Any]:
    return _load_from_file(toml_override_path).get("tool", {}).get("rattr", {})
