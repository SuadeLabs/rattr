from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING

import pytest

from rattr.module_locator.models import ModuleSpec
from rattr.module_locator.util import (
    derive_module_names_left,
    derive_module_names_right,
    find_module_name_and_spec,
    find_module_spec_fast,
    format_origin_for_os,
    is_in_import_blacklist,
    is_in_pip,
    is_in_stdlib,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Final

    from tests.shared import ArgumentsFn


known_targets_in_stdlib_modules: Final = (
    "os.path",
    "os.path.join",
    "math.sin",
    "math.pi",
)

known_pip_modules: Final = (
    "isort",
    "pytest",
)
known_pip_targets: Final = (
    "isort.place.place_module",
    "pytest.mark.parameterize",
)
known_pip_modules_absent_in_venv: Final = (
    "numpy",
    "pandas",
)

known_rattr_modules: Final = (
    "rattr",
    "rattr.ast.util",
    "rattr.models.context",
)
known_rattr_targets: Final = (
    "rattr.ast.util.basename_of",
    "rattr.models._context.Context",
)


@pytest.mark.parametrize(
    "target,expected",
    testcases := [
        # the empty string
        ("", [""]),
        # general
        ("non_dotted_name", ["non_dotted_name"]),
        ("a.b.c.d", ["a.b.c.d", "b.c.d", "c.d", "d"]),
        # stdlib
        ("os.path.join", ["os.path.join", "path.join", "join"]),
        ("pathlib.Path", ["pathlib.Path", "Path"]),
        # internal
        ("rattr.util.is_name", ["rattr.util.is_name", "util.is_name", "is_name"]),
    ],
    ids=[t[0] for t in testcases],
)
def test_derive_module_names_left(target: str, expected: list[str]):
    assert derive_module_names_left(target) == expected


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
        ("pathlib.Path", ["pathlib.Path", "pathlib"]),
        # internal
        ("rattr.util.is_name", ["rattr.util.is_name", "rattr.util", "rattr"]),
    ],
    ids=[t[0] for t in testcases],
)
def test_derive_module_names_right(target: str, expected: list[str]):
    assert derive_module_names_right(target) == expected


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
    # NOTE
    # Use `find_spec` not `find_module_spec_fast` here as we are testing the correctness
    # of the latter's impl.
    stdlib_spec = importlib.util.find_spec(module_name)
    rattr_spec = (
        ModuleSpec(
            name=stdlib_spec.name,
            origin=format_origin_for_os(stdlib_spec.origin),
        )
        if stdlib_spec is not None
        else None
    )
    assert find_module_name_and_spec(target) == (module_name, rattr_spec)


@pytest.mark.parametrize(
    "modulename",
    testcases := [
        # non-existant
        "",
        "does_not_exist",
        "does.not.exist",
        # stdlib
        "math",
        "math.pi",
        "os.path",
        # local (rattr)
        "rattr.does.not.exist",
        "rattr.ast",
        "rattr.ast.util",
        "rattr.analyser.annotations.rattr_ignore",
        # pip installed
        "isort",
        "isort.place",
        "attrs",
    ],
    ids=testcases,
)
def test_find_module_spec_fast(modulename: str):
    try:
        stdlib_spec = importlib.util.find_spec(modulename)
    except (AttributeError, ModuleNotFoundError, ValueError):
        stdlib_spec = None

    expected = (
        ModuleSpec(
            name=stdlib_spec.name,
            origin=format_origin_for_os(stdlib_spec.origin),
        )
        if stdlib_spec is not None
        else None
    )

    assert find_module_spec_fast(modulename) == expected


@pytest.mark.linux
@pytest.mark.parametrize(
    "modulename, expected",
    testcases := [
        # stdlib
        ("sys", importlib.util.find_spec("sys").origin),
        ("math", importlib.util.find_spec("math").origin),
        ("os.path", importlib.util.find_spec("os.path").origin),
        # local (rattr)
        ("rattr.ast", importlib.util.find_spec("rattr.ast").origin),
        ("rattr.ast.util", importlib.util.find_spec("rattr.ast.util").origin),
        # pip installed
        (
            "isort",
            importlib.util.find_spec("isort").origin,
        ),
        (
            "isort.place",
            importlib.util.find_spec("isort.place").origin,
        ),
        (
            "attrs",
            importlib.util.find_spec("attrs").origin,
        ),
    ],
    ids=[t[0] for t in testcases],
)
def test_find_module_spec_fast_origins(modulename: str, expected: str):
    assert find_module_spec_fast(modulename).origin == expected


@pytest.mark.parametrize(
    "modulename, expected",
    testcases := [
        ("", False),
        ("anything.dotted.anything", False),
        *[(stdlib_target, True) for stdlib_target in known_targets_in_stdlib_modules],
        ("math.this.is.not.in.the.stdlib", True),
        *[
            (pip_target, False)
            for pip_target in known_pip_modules
            + known_pip_targets
            + known_pip_modules_absent_in_venv
        ],
        *[
            (rattr_target, False)
            for rattr_target in known_rattr_modules + known_rattr_targets
        ],
    ],
    ids=[t[0] for t in testcases],
)
def test_is_in_stdlib(modulename: str, expected: bool):
    assert is_in_stdlib(modulename) == expected


def test_is_in_stdlib_known_stdlib_modules(stdlib_modules: Iterable[str]):
    for modulename in stdlib_modules:
        assert is_in_stdlib(modulename)


@pytest.mark.parametrize(
    "modulename, expected",
    testcases := [
        ("", False),
        ("anything.dotted.anything", False),
        *[(stdlib_target, False) for stdlib_target in known_targets_in_stdlib_modules],
        ("math.this.is.not.in.the.stdlib", False),
        *[(pip_target, True) for pip_target in known_pip_modules + known_pip_targets],
        *[(pip_target, False) for pip_target in known_pip_modules_absent_in_venv],
        *[
            (rattr_target, False)
            for rattr_target in known_rattr_modules + known_rattr_targets
        ],
    ],
    ids=[t[0] for t in testcases],
)
def test_is_in_pip(modulename: str, expected: bool):
    assert is_in_pip(modulename) == expected


def test_is_in_pip_known_stdlib_modules(stdlib_modules: Iterable[str]):
    for modulename in stdlib_modules:
        assert not is_in_pip(modulename)


@pytest.mark.parametrize(
    "modulename, expected",
    testcases := [
        ("", True),
        ("anything.dotted.anything", False),
        *[(stdlib_target, False) for stdlib_target in known_targets_in_stdlib_modules],
        ("math.this.is.not.in.the.stdlib", False),
        *[
            (pip_target, False)
            for pip_target in known_pip_modules
            + known_pip_targets
            + known_pip_modules_absent_in_venv
        ],
        *[
            (rattr_target, True)
            for rattr_target in known_rattr_modules + known_rattr_targets
        ],
    ],
    ids=[t[0] for t in testcases],
)
def test_is_in_import_blacklist(modulename: str, expected: bool):
    assert is_in_import_blacklist(modulename) == expected


def test_is_in_import_blacklist_known_stdlib_modules(stdlib_modules: Iterable[str]):
    for modulename in stdlib_modules:
        assert not is_in_import_blacklist(modulename)


@pytest.mark.parametrize(
    "banned,unbanned",
    [
        (
            {"beelzebub", "abaddon"},
            {"michael", "raphael", "gabriel"},
        )
    ],
)
def test_is_in_import_blacklist_from_cli_argument(
    arguments: ArgumentsFn,
    banned: set[str],
    unbanned: set[str],
):
    is_in_import_blacklist.cache_clear()

    # Nothing is banned
    with arguments(_excluded_imports=set()):
        for banned_module in sorted(banned):
            assert not is_in_import_blacklist(banned_module)
        for unbanned_module in sorted(unbanned):
            assert not is_in_import_blacklist(unbanned_module)

    is_in_import_blacklist.cache_clear()

    # Only bad things are banned
    with arguments(_excluded_imports=banned):
        for banned_module in sorted(banned):
            assert is_in_import_blacklist(banned_module)
        for unbanned_module in sorted(unbanned):
            assert not is_in_import_blacklist(unbanned_module)
