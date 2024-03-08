from __future__ import annotations

import re
import sys
from functools import cache
from importlib.util import find_spec as stdlib_find_spec
from pathlib import Path
from typing import TYPE_CHECKING

from isort import sections
from isort.api import place_module

from rattr.config import Config
from rattr.module_locator._locate import (  # noqa: F401
    find_module_in_path,
    iter_python_path_dirs,
    locate_module_in_python_path,
)
from rattr.module_locator.models import ModuleSpec

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from typing import Final

    from rattr.ast.types import FullyQualifiedName, ModuleName
    from rattr.versioning.typing import TypeAlias

    ImportLevel: TypeAlias = int


RE_PIP_INSTALL_LOCATIONS: Final = (re.compile(r".+/site-packages.*"),)


def module_exists(modulename: ModuleName) -> bool:
    return find_module_spec_fast(modulename) is not None


@cache
def find_module_spec_fast(modulename: ModuleName) -> ModuleSpec | None:
    if is_in_stdlib(modulename):
        return __find_stdlib_module_spec_impl(modulename)

    locations = locate_module_in_python_path(modulename)

    if not locations:
        return None

    return ModuleSpec(name=modulename, origin=format_origin_for_os(locations[0]))


@cache
def __find_stdlib_module_spec_impl(modulename: ModuleName) -> ModuleSpec | None:
    try:
        stdlib_spec = stdlib_find_spec(modulename)
    except (AttributeError, ModuleNotFoundError, ValueError):
        return None

    if stdlib_spec is None:
        return None

    return ModuleSpec(
        name=stdlib_spec.name,
        origin=format_origin_for_os(stdlib_spec.origin),
    )


@cache
def format_origin_for_os(origin: str | Path | None) -> str | None:
    if origin is None:
        return origin

    if isinstance(origin, Path):
        origin = str(origin)

    if sys.platform != "win32":
        return origin

    # HACK
    # Windows paths are case-insensitive so force lower case for comparisons etc
    return origin[:2] + origin[2:].lower()


@cache
def find_module_name_and_spec(
    target: FullyQualifiedName,
) -> tuple[ModuleName, ModuleSpec] | tuple[None, None]:
    """Return the module name and spec for the given fully qualified name.

    The fully qualified name is that of the module:
    >>> find_module_name_and_spec("math")
    ("math", ModuleSpec(name='math', loader=... origin='built-in')

    The fully qualified name is that of a module member:
    >>> find_module_name_and_spec("math.pi")
    ("math", ModuleSpec(name='math', loader=... origin='built-in')

    The fully qualified name is that of a member of a nested module:
    >>> find_module_name_and_spec("os.path.join")
    ("os.path", ModuleSpec(name='posixpath', loader=..., origin=...))

    The given name is not a fully qualified name:
    >>> find_module_name_and_spec("join")
    (None, None)
    """
    # Can't so anything with relative imports
    if target.startswith("."):
        return None, None

    for modulename in iter_module_names_right(target.split(".")):
        if (spec := find_module_spec_fast(modulename)) is not None:
            return modulename, spec

    return None, None


def iter_module_names_right(module_parts: Iterable[str]) -> Iterator[ModuleName]:
    """Return the possible module qualified names for the given parts.

    >>> list(iter_possible_modules([]))
    []

    >>> list(iter_possible_modules(["module"]))
    ["module"]

    >>> list(iter_possible_modules(["module", "sub_module"]))
    ['module.sub_module', 'module']

    >>> list(iter_possible_modules(["module", "sub_module", "file"]))
    ['module.sub_module.file', 'module.sub_module', 'module']
    """
    yield ".".join(module_parts)
    for end_offset in range(1, len(module_parts)):
        yield ".".join(module_parts[:-end_offset])


def derive_module_names_right(modulename: ModuleName) -> list[ModuleName]:
    return list(iter_module_names_right(modulename.split(".")))


@cache
def derive_module_name_from_path(filepath: Path | str | None) -> str | None:
    """Return the recognised name of the given module."""
    if filepath is None:
        raise ValueError("unable to derive the module of 'None'")

    filepath = Path(filepath)
    filepath_str = str(filepath)

    # Given a file '/path/to/repo/my_module/file/__init.py', the longest possible module
    # name would be 'path.to.repo.my_module.file' though in reality it may just be
    # 'my_module.file'
    longest_possible_modulename = (
        filepath_str.replace("/", ".")
        .replace("\\", ".")
        .removesuffix(".__init__.py")
        .removesuffix(".py")
        .strip(".")  # strip remaining "." in relative files
    )

    for module in iter_module_names_left(longest_possible_modulename.split(".")):
        if module_exists(module):
            return module

    return None


def iter_module_names_left(module_parts: Iterable[str]) -> Iterator[ModuleName]:
    """Return the possible module qualified names for the given parts.

    >>> list(iter_possible_modules([]))
    []

    >>> list(iter_possible_modules(["module"]))
    ["module"]

    >>> list(iter_possible_modules(["module", "sub_module"]))
    ['module.sub_module', 'sub_module']

    >>> list(iter_possible_modules(["module", "sub_module", "file"]))
    ['module.sub_module.file', 'sub_module.file', 'file']
    """
    for start_offset in range(len(module_parts)):
        yield ".".join(module_parts[start_offset:])


@cache
def derive_module_names_left(modulename: ModuleName) -> list[ModuleName]:
    return list(iter_module_names_left(modulename.split(".")))


@cache
def derive_absolute_module_name(
    base: ModuleName,
    target: ModuleName | None,
    level: ImportLevel,
) -> ModuleName:
    config = Config()

    if config.state.current_file.name == "__init__.py":
        level -= 1

    if level > 0:
        base = ".".join(base.split(".")[:-level])

    return f"{base}.{target}" if target is not None else base


@cache
def is_in_stdlib(name: ModuleName) -> bool:
    """Return `True` if the given name is an stdlib module or in an stdlib module.

    >>> is_stdlib_module("math")
    True
    >>> is_stdlib_module("math.pi")
    True
    >>> is_stdlib_module("pytest.fixture")
    False
    """
    return place_module(name) == sections.STDLIB


@cache
def is_in_pip(name: ModuleName) -> bool:
    """Return `True` if the given name is available via pip.

    >>> # Given that pytest is pip installed
    >>> is_in_pip("pytest")
    True
    >>> is_in_pip("pytest.fixture")
    True
    >>> is_in_pip("math")
    False
    >>> is_in_pip("something.made.up")
    False
    """
    return any(
        re_pip_location.fullmatch(origin)
        for module in derive_module_names_right(name)
        for re_pip_location in RE_PIP_INSTALL_LOCATIONS
        if (origin := __safe_origin(module)) is not None
    )


@cache
def is_in_import_blacklist(name: ModuleName) -> bool:
    """Return `True` if the given name matches a blacklisted pattern."""
    config = Config()

    # Somewhat undefined behaviour, but don't follow null strings
    if not name:
        return True

    # Exclude stdlib modules such as the built-in "_thread" (stdlib modules are handled
    # separately from blacklist).
    if is_in_stdlib(name):
        return False

    origins = [__safe_origin(module) for module in derive_module_names_right(name)]

    # It is possible that we can't determine the spec (due to some PYTHON_PATH
    # tampering or some other shenanigans) and in that case we still want to assume that
    # the origin is exactly as given as it may still be blacklisted.
    origins.append(name)

    return any(
        re_pattern.fullmatch(origin)
        for origin in origins
        for re_pattern in config.re_blacklist_patterns
        if origin is not None
    )


@cache
def __safe_origin(module: ModuleName) -> str | None:
    spec = find_module_spec_fast(module)

    if spec is None or spec.origin is None:
        return None

    # No backslashes, bad windows!
    return spec.origin.replace("\\", "/")
