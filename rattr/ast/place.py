"""Utils to find the location/place of a name, import, etc."""
from __future__ import annotations

import re
from itertools import product
from typing import TYPE_CHECKING

from isort import sections
from isort.api import place_module

from rattr.config import Config
from rattr.module_locator.util import derive_module_names_right, find_module_spec_fast

if TYPE_CHECKING:
    from typing import Final

    from rattr.ast.types import Identifier


RE_PIP_INSTALL_LOCATIONS: Final = (re.compile(r".+/site-packages.*"),)


def is_in_stdlib(name: Identifier) -> bool:
    """Return `True` if the given name is an stdlib module or in an stdlib module.

    >>> is_stdlib_module("math")
    True
    >>> is_stdlib_module("math.pi")
    True
    >>> is_stdlib_module("pytest.fixture")
    False
    """
    return place_module(name) == sections.STDLIB


def is_in_pip(name: Identifier) -> bool:
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

    origins = [_safe_origin(module) for module in derive_module_names_right(name)]

    return any(
        re_pip_location.fullmatch(origin)
        for origin, re_pip_location in product(origins, RE_PIP_INSTALL_LOCATIONS)
        if origin is not None
    )


def is_in_import_blacklist(name: Identifier) -> bool:
    """Return `True` if the given name matches a blacklisted pattern."""
    config = Config()

    # Somewhat undefined behaviour, but don't follow null strings
    if not name:
        return True

    # Exclude stdlib modules such as the built-in "_thread" (stdlib modules are handled
    # separately from blacklist).
    if is_in_stdlib(name):
        return False

    origins = [_safe_origin(module) for module in derive_module_names_right(name)]

    # It is possible that we can't determine the spec (due to some PYTHON_PATH
    # tampering or some other shenanigans) and in that case we still want to assume that
    # the origin is exactly as given as it may still be blacklisted.
    origins.append(name)

    return any(
        re_pattern.fullmatch(origin)
        for origin, re_pattern in product(origins, config.re_blacklist_patterns)
        if origin is not None
    )


def _safe_origin(module: Identifier) -> str | None:
    spec = find_module_spec_fast(module)

    if spec is None or spec.origin is None:
        return None

    # No backslashes, bad windows!
    return spec.origin.replace("\\", "/")
