from __future__ import annotations

import pytest


@pytest.fixture
def illegal_field_name():
    return "illegal-field"


@pytest.fixture
def required_sys_args():
    return ["my/rattr/target.py"]


@pytest.fixture
def toml_with_illegal_field(illegal_field_name, toml_well_formed: dict):
    return {**toml_well_formed, **{illegal_field_name: "any-old-value"}}


@pytest.fixture
def toml_well_formed():
    return {
        "follow-imports": 3,
        "exclude-imports": [
            r"a\.b\.c",
            r"a\.b.*",
            r"a\.b\.c\.e",
            r"a\.b\.c.*",
        ],
        "exclude": [r"a_.*", r"b_.*", r"_.*"],
        "warning-level": "all",
        "threshold": 1,
    }
