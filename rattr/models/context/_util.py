from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from rattr.ast.types import AstLiterals, Identifier
from rattr.config import Config
from rattr.models.symbol._symbols import (
    PYTHON_BUILTINS,
    PYTHON_NON_PRIMITIVE_RETURNING_BUILTINS,
    Import,
)
from rattr.module_locator.util import module_exists

if TYPE_CHECKING:
    from rattr.models.symbol._symbol import Symbol


def is_call_to_literal(name: Identifier) -> bool:
    """Return `True` if this appears to be a call to a literal."""
    return name.startswith("@")


def is_call_to_subscript_item(name: Identifier) -> bool:
    """Return `True` if this appears to be a call to a literal."""
    return "[]" in name


def is_call_to_method(
    target: Symbol | None,
    name: Identifier,
    lhs_target: Symbol | None,
    lhs_name: Identifier,
) -> bool:
    """Return `True` if this appears to be a call to a method."""
    return name != lhs_name and target is None and not isinstance(lhs_target, Import)


def is_call_to_method_on_imported_member(
    target: Symbol | None,
    name: Identifier,
    lhs_target: Symbol | None,
    lhs_name: Identifier,
) -> bool:
    """Return `True` if this appears to be a call to a method on an imported symbol."""
    return (
        name != lhs_name
        and target is None
        and isinstance(lhs_target, Import)
        and not module_exists(lhs_target.qualified_name)
    )


def is_call_to_member_of_module_import(
    name: Identifier,
    target: Symbol | None,
) -> bool:
    """Return `True` if this appears to be a call to a module member.

    Only applicable to members of modules imported like so:
    >>> import math

    Not those imported like so:
    >>> from math import pi

    Examples:
    >>> # Context from `import math`
    >>> # thus `math.pi` is not explicitly defined
    >>> # thus the rhs is `None`
    >>> is_call_to_member_of_module_import("math.pi", None)
    True

    >>> # Context from `from math import pi`
    >>> # thus `math.pi` is defined in the context
    >>> # thus the rhs is the import symbol for `pi`
    >>> is_call_to_member_of_module_import("pi", Import(...))
    False
    """
    return "." in name and target is None


def is_direct_call_to_method_on_constant(name: str) -> bool:
    """Return `True` if the name is a call to method on a constant."""
    config = Config()

    _prefix = config.LITERAL_VALUE_PREFIX
    _constant = f"{_prefix}{ast.Constant.__name__}."

    return name.startswith(_constant)


def is_direct_call_to_method_on_literal(name: str) -> bool:
    """Return `True` if the name is a call to method on a constant."""
    config = Config()

    _prefix = config.LITERAL_VALUE_PREFIX
    _literals = tuple(f"{_prefix}{literal.__name__}." for literal in AstLiterals)

    return name.startswith(_literals)


def is_call_to_method_on_primitive_from_call(name: str) -> bool:
    """Return `True` if the name is a call to a method on a call result's primitive.

    This will have lots of false-negatives, but it will detect calls to methods on the
    results of casts or other applicable builtins.
    """
    builtins = {b for b in PYTHON_BUILTINS if b[0].isalpha()}
    builtins -= PYTHON_NON_PRIMITIVE_RETURNING_BUILTINS

    return any(name.startswith((f"{b}.", f"{b}().")) for b in builtins)


def is_call_to_method_on_py_type(name: str) -> bool:
    """Return `True` if the given name is a method on a primitive type."""
    if is_direct_call_to_method_on_constant(name):
        return True

    if is_direct_call_to_method_on_literal(name):
        return True

    if is_call_to_method_on_primitive_from_call(name):
        return True

    return False


def is_call_to_call_result(call: ast.AST) -> bool:
    """Return `True` if the given call is a call to another call's result."""
    return isinstance(call, ast.Call) and isinstance(call.func, ast.Call)
