from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from rattr.ast._util import (  # noqa: F401
    get_python_attr_access_fn_obj_attr_pair,
    is_call_to_fn,
    is_string_literal,
    names_of,
)
from rattr.ast.types import AstStrictlyNameable

if TYPE_CHECKING:
    from typing import Callable

    from rattr.versioning.typing import TypeAlias

    _Identifier: TypeAlias = str

    _NameGetter: TypeAlias = Callable[[ast.expr], _Identifier]


def basename_of(node: ast.expr, *, safe: bool = False) -> _Identifier:
    """Return the basename of the given expression."""
    return names_of(node, safe=safe)[0]


def fullname_of(node: ast.expr, *, safe: bool = False) -> _Identifier:
    """Return the fullname of the given expression."""
    return names_of(node, safe=safe)[1]


def unravel_names(
    node: ast.expr,
    *,
    _get_name: _NameGetter = basename_of,
) -> list[str]:
    """Return the name of each nameable in a given expression.

    >>> ravelled_names = ast.parse("a, b = 1, 2").body[0].targets[0]
    >>> unravel_names(ravelled_names)
    ["a", "b"]

    >>> ravelled_names = ast.parse("(a, b), c, d.e = ...").body[0].targets[0]
    >>> unravel_names(ravelled_names)
    ["a", "b", "c", "d"]

    >>> # The name getter can be overridden for example as `fullname_of`:
    >>> ravelled_names = ast.parse("a.attr = 1").body[0].targets[0]
    >>> list(unravel_names(ravelled_names))
    ["a"]
    >>> unravel_names(ravelled_names, _get_name=fullname_of)
    ["a.attr"]
    >>> # And in the complex example from above, notice "d.e" not just "d"
    >>> ravelled_names = ast.parse("(a, b), c, d.e = ...").body[0].targets[0]
    >>> unravel_names(ravelled_names, _get_name=fullname_of)
    ["a", "b", "c", "d.e"]
    """
    if isinstance(node, AstStrictlyNameable):
        return [_get_name(node)]

    if isinstance(node, (ast.Tuple, ast.List)):
        return [
            name
            for elt in node.elts
            for name in unravel_names(elt, _get_name=_get_name)
        ]

    raise TypeError(f"line {node.lineno}: {ast.dump(node)}")
