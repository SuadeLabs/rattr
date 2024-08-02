from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from rattr.ast._util import (  # noqa: F401
    get_python_attr_access_fn_obj_attr_pair,  # type: ignore[reportUnusedImport]
    is_call_to_fn,  # type: ignore[reportUnusedImport]
    is_string_literal,  # type: ignore[reportUnusedImport]
    names_of,
)
from rattr.ast.types import AstNodeWithName

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Final

    from rattr.ast.types import Identifier
    from rattr.versioning.typing import TypeAlias

    _NameGetter: TypeAlias = Callable[[ast.expr], Identifier]


NAMEDTUPLE_INVALID_SIGNATURE_ERROR: Final = (
    "namedtuple expects exactly two positional arguments (i.e. name, attrs)"
)
NAMEDTUPLE_INVALID_SECOND_PARAMETER_VALUE_ERROR: Final = (
    "namedtuple expects the second positional argument to be a list of valid "
    "identifiers as either a Python list of strings or a string literal of space "
    "delimited strings"
)


def basename_of(
    node: ast.expr,
    *,
    unravel_attr_access_calls: bool = True,
    safe: bool = False,
) -> Identifier:
    """Return the basename of the given expression."""
    basename, _ = names_of(
        node,
        unravel_attr_access_calls=unravel_attr_access_calls,
        safe=safe,
    )
    return basename


def fullname_of(
    node: ast.expr,
    *,
    unravel_attr_access_calls: bool = True,
    safe: bool = False,
) -> Identifier:
    """Return the fullname of the given expression."""
    _, fullname = names_of(
        node,
        unravel_attr_access_calls=unravel_attr_access_calls,
        safe=safe,
    )
    return fullname


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
    if isinstance(node, AstNodeWithName):
        return [_get_name(node)]

    if isinstance(node, (ast.Tuple, ast.List)):
        return [
            name
            for elt in node.elts
            for name in unravel_names(elt, _get_name=_get_name)
        ]

    raise TypeError(f"line {node.lineno}: {ast.dump(node)}")


def is_starred_import(node: ast.stmt) -> bool:
    """Return `True` if the given ast node is a starred import.

    >>> is_starred_import(ast.parse("from math import *").body[0])
    True
    >>> is_starred_import(ast.parse("from math import pi, pow").body[0])
    False
    """
    return (
        isinstance(node, ast.ImportFrom)
        and len(node.names) == 1
        and node.names[0].name == "*"
    )


def is_relative_import(node: ast.stmt) -> bool:
    """Return `True` if the given ast node is a relative import.

    >>> is_relative_import(ast.parse("from math import pi").body[0])
    False
    >>> is_relative_import(ast.parse("from .my_maths import pi").body[0])
    True
    """
    # As per documentation[1] `ImportFrom.level` is the level of the relative import,
    # where 0 means it is an absolute import.
    # [1] - https://docs.python.org/3/library/ast.html#ast.ImportFrom
    return isinstance(node, ast.ImportFrom) and node.level != 0


def assignment_targets(
    assignment: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
) -> list[ast.expr]:
    """Return the assignment targets (assignment lhs)."""
    if isinstance(assignment, ast.Assign):
        return assignment.targets
    if isinstance(assignment, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
        return [assignment.target]
    else:
        raise TypeError(f"line {assignment.lineno}: {ast.dump(assignment)}")


def assignment_is_one_to_one(
    assignment: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
) -> bool:
    """Return `True` if the given assignment is one-to-one."""
    targets = assignment_targets(assignment)

    def _is_iterable(target: ast.expr | None) -> bool:
        return isinstance(target, (ast.Tuple, ast.List))

    lhs_is_singular = len(targets) == 1 and not _is_iterable(targets[0])
    rhs_is_singular = not _is_iterable(assignment.value)

    return lhs_is_singular and rhs_is_singular


def has_lambda_in_rhs(
    assignment: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
) -> bool:
    """Return `True` if the given assignment has a lambda in the right-hand side."""
    if isinstance(assignment.value, ast.Lambda):
        return True
    elif isinstance(assignment.value, (ast.Tuple, ast.List)):  # iterable unpacking
        return any(isinstance(v, ast.Lambda) for v in assignment.value.elts)
    else:
        return False


def has_walrus_in_rhs(
    assignment: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
) -> bool:
    """Return `True` if the given assignment contains a walrus assignment in the rhs."""
    if isinstance(assignment.value, ast.NamedExpr):
        return True
    elif isinstance(assignment.value, (ast.Tuple, ast.List)):
        return any(isinstance(v, ast.NamedExpr) for v in assignment.value.elts)
    else:
        return False


def walruses_in_rhs(
    assignment: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
) -> list[ast.NamedExpr]:
    """Return the walruses in the rhs of the given assignment.

    >>> walruses_in_rhs(ast.parse("a = (b := c)").body[0].value)
    [NamedExpr(target=Name(id='b', ctx=Store()), value=Name(id='c', ctx=Load())), ]

    >>> walruses_in_rhs(ast.parse("a = (b, c := d)").body[0].value)
    [NamedExpr(target=Name(id='c', ctx=Store()), value=Name(id='d', ctx=Load())), ]
    """
    if not has_walrus_in_rhs(assignment):
        return []

    if isinstance(assignment.value, (ast.Tuple, ast.List)):
        values = assignment.value.elts
    else:
        values = [assignment.value]

    return [e for e in values if isinstance(e, ast.NamedExpr)]


def has_namedtuple_declaration_in_rhs(
    assignment: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
) -> bool:
    """Return `True` if the rhs contains a call to create a namedtuple type."""

    def _target_is_namedtuple(call: ast.Call) -> bool:
        # HACK
        # Naive approach, replace when enum / class namedtuple / etc is improved.
        # See: cls.py::is_enum, cls.py::is_namedtuple
        name = fullname_of(call.func, safe=True)
        return name == "namedtuple" or name.endswith(".namedtuple")

    if isinstance(assignment.value, ast.Call):
        return _target_is_namedtuple(assignment.value)
    elif isinstance(assignment.value, (ast.Tuple, ast.List)):
        return any(
            _target_is_namedtuple(value)
            for value in assignment.value.elts
            if isinstance(value, ast.Call)
        )
    else:
        return False


def namedtuple_init_signature_from_declaration(
    assignment: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
) -> list[str]:
    """Return the args/attrs of the namedtuple constructed by this assignment by call.

    Note:
        Assumes one-to-one assignment.

    >>> node = ast.parse("p = namedtuple('p', ['x', 'y'])").body[0].value
    >>> namedtuple_init_signature_from_declaration(node)
    ["self", "x", "y]

    Raises:
        TypeError: The node is not an assignment of a call.
        ValueError: Invalid namedtuple declaration.

    Returns:
        tuple[list[str], dict[str, str]]: The positional and keyword args of the init.
    """

    def namedtuple_attrs_from_second_argument(attrs: ast.expr) -> list[str]:
        if isinstance(attrs, ast.List):
            return unpack_ast_list_of_strings(attrs)

        if isinstance(attrs, ast.Constant):
            return parse_space_delimited_ast_string(attrs)

        raise SyntaxError

    # Parse call arguments
    if not isinstance(assignment.value, ast.Call):
        raise TypeError

    namedtuple_call_arguments = assignment.value.args

    if len(namedtuple_call_arguments) != 2:
        raise ValueError(NAMEDTUPLE_INVALID_SIGNATURE_ERROR)

    _, namedtuple_attrs_argument = namedtuple_call_arguments

    try:
        attrs = namedtuple_attrs_from_second_argument(namedtuple_attrs_argument)
    except SyntaxError as exc:
        raise ValueError(NAMEDTUPLE_INVALID_SECOND_PARAMETER_VALUE_ERROR) from exc

    return ["self", *attrs]


def unpack_ast_list_of_strings(ast_attrs: ast.List) -> list[str]:
    """Return the given ast.List of ast.Constant strings as a Python list[str]."""
    unpacked_attrs: list[str] = [
        arg.value
        for arg in ast_attrs.elts
        if isinstance(arg, ast.Constant)
        if isinstance(arg.value, str)
    ]

    if len(unpacked_attrs) != len(ast_attrs.elts):
        raise SyntaxError

    return unpacked_attrs


def parse_space_delimited_ast_string(ast_string: ast.Constant) -> list[str]:
    """Return the given ast.Constant string as a Python str."""
    if not isinstance(ast_string.value, str):
        raise SyntaxError

    if ast_string.value == "":
        return []

    parsed_attrs = ast_string.value.split(" ")

    if not all(attr.isidentifier() for attr in parsed_attrs):
        raise SyntaxError

    return parsed_attrs
