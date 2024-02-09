from __future__ import annotations

import importlib.util

import pytest

from rattr.module_locator.util import (
    derive_possible_module_names,
    find_module_name_and_spec,
)


@pytest.mark.parametrize(
    "target,expected",
    testcases := [
        # the empty string
        ("", [""]),
        # general
        ("non_dotted_name", ["non_dotted_name"]),
        ("a.b.c.d", ["a.b.c.d", "a.b.c", "a.b", "a"]),
        # stdlib
        ("os.path.join", ["os.path.join", "os.path", "os"]),
        ("pathlib.Path.", ["pathlib.Path", "pathlib"]),
        # internal
        ("rattr.util.is_name", ["rattr.util.is_name", "rattr.util", "rattr"]),
    ],
    ids=[t[0] for t in testcases],
)
def test_derive_possible_module_names(target: str, expected: list[str]):
    assert derive_possible_module_names(target) == expected


@pytest.mark.parametrize(
    "target",
    [
        # the empty string
        "",
        # non-existant module
        "i.am.not.a.module",
    ],
)
def test_find_module_name_and_spec_non_existant(target: str):
    assert find_module_name_and_spec(target) == (None, None)


@pytest.mark.parametrize(
    "target,module_name",
    [
        # stdlib
        ("math", "math"),
        ("math.pi", "math"),
        ("os", "os"),
        ("os.path", "os.path"),
        # internal
        ("rattr.analyser", "rattr.analyser"),
        ("rattr.analyser.util.get_module_spec", "rattr.analyser.util"),
    ],
)
def test_find_module_name_and_spec_real_world(target: str, module_name: str):
    assert find_module_name_and_spec(target) == (
        module_name,
        importlib.util.find_spec(module_name),
    )
