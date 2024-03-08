from __future__ import annotations

import ast
from functools import lru_cache
from typing import TYPE_CHECKING

from rattr import error
from rattr.ast.types import (
    AstComprehensions,
    AstLiterals,
)
from rattr.config import Config
from rattr.models.symbol._symbols import PYTHON_ATTR_ACCESS_BUILTINS

if TYPE_CHECKING:
    from rattr.ast.types import Identifier


def is_call_to_fn(node: ast.Call, target: Identifier) -> bool:
    """Return `True` if the given node is a direct call to `target`."""
    if not isinstance(node, ast.Call):
        raise TypeError(f"line {node.lineno}: {ast.dump(node)}")

    if not isinstance(node.func, ast.Name):
        return False

    return node.func.id == target


def is_string_literal(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def get_python_attr_access_fn_obj_attr_pair(
    fn: str,
    node: ast.Call,
    *,
    warn: bool = False,
) -> tuple[Identifier, Identifier]:
    """Return the object-attr pair from the call to getattr, etc.

    ### Examples
    >>> # Simple getattr call
    >>> call = ast.parse("getattr(a, 'b')").body[0].value
    >>> get_python_attr_access_fn_obj_name_pair("getattr", call)
    ("a", "b")

    >>> # Nested getattr call
    >>> call = ast.parse("getattr(getattr(a, 'b'), 'c')").body[0].value
    >>> get_python_attr_access_fn_obj_name_pair("getattr", call)
    ("a.b", "c")

    >>> # Complex nested getattr call
    >>> call = ast.parse("getattr(getattr(a.b[0], 'c'), 'd')").body[0].value
    >>> get_python_attr_access_fn_obj_name_pair("getattr", call)
    ("a.b[].c", "d")

    >>> # Non-literal in RHS
    >>> # Additionally, this will give a rattr.error
    >>> call = ast.parse("getattr(a, some_string_variable)").body[0].value
    >>> get_python_attr_access_fn_obj_name_pair("getattr", call)
    ("a", "<some_string_variable>")
    """
    this = f"{fn!r}"

    try:
        obj, name, *_ = node.args
    except ValueError:
        error.fatal(f"invalid call to {this}, too few args", node)

    if warn and not isinstance(name, ast.Constant):
        error.error(f"{this} expects 'name' to be a string literal", node)

    _, varname = names_of(name, safe=True)
    attr: str = name.value if is_string_literal(name) else f"<{varname}>"

    if isinstance(obj, ast.Call) and not is_call_to_fn(obj, fn):
        error.fatal(f"{this} may only be nested in other calls to {this}", node)

    if isinstance(obj, ast.Call):
        lhs = ".".join(get_python_attr_access_fn_obj_attr_pair(fn, obj, warn=warn))
    else:
        _, lhs = names_of(obj, safe=False)

    return lhs, attr


@lru_cache(maxsize=None)
def names_of(
    node: ast.expr,
    *,
    unravel_attr_access_calls: bool = True,
    safe: bool = False,
) -> tuple[Identifier, Identifier]:
    """Return the node's basename and fullname.

    Uses indirect recursion, see:
    * __ast_call_name
    * __ast_compound_name
    * get_python_attr_access_fn_obj_name_pair

    ### Examples
    >>> # Simple examples of strictly-nameable expressions
    >>> # These are the same for both safe=False and safe=True
    >>> names_of(ast.parse("my_variable").body[0].value)
    ("my_variable", "my_variable")
    >>> names_of(ast.parse("my_variable.attr").body[0].value)
    ("my_variable", "my_variable.attr")
    >>> names_of(ast.parse("my_variable[100].attr").body[0].value)
    ("my_variable", "my_variable[].attr")
    >>> names_of(ast.parse("*my_variable[100].attr").body[0].value)
    ("my_variable", "*my_variable[].attr")

    >>> # Not a strictly nameable expression
    >>> # With safe=False (default)
    >>> names_of(ast.parse("(a, b)[0].attr").body[0].value)
    error.RattrLiteralInNameable: ...
    >>> # With safe=True
    >>> names_of(ast.parse("(a, b)[0].attr").body[0].value, safe=True)
    ("@Tuple", "@Tuple[].attr")
    """
    if isinstance(node, ast.Name):
        return node.id, node.id

    if isinstance(node, ast.Call):
        return __ast_call_name(
            node,
            unravel_attr_access_calls=unravel_attr_access_calls,
            safe=safe,
        )

    if isinstance(
        node,
        (ast.Attribute, ast.Subscript, ast.Starred),
    ):
        return __ast_compound_name(node, safe=safe)

    # The expression is unnamable, if in safe mode give a "best-guess" as to avoid an
    # error, but when not in safe mode pick an appropriate error type.

    if safe:
        return __safe_name(node), __safe_name(node)

    raise __specific_name_error(node)(f"line {node.lineno}: {ast.dump(node)}")


@lru_cache(maxsize=1)
def __safe_name(node: ast.expr) -> Identifier:
    """Return a safe name for this unnameable expression."""
    config = Config()

    _local_value_prefix = config.LITERAL_VALUE_PREFIX
    _node_class_name = node.__class__.__name__

    return f"{_local_value_prefix}{_node_class_name}"


def __ast_call_name(
    node: ast.Call,
    *,
    unravel_attr_access_calls: bool = False,
    safe: bool = True,
) -> tuple[Identifier, Identifier]:
    basename, lhs_name = names_of(node.func, safe=safe)

    # Special case: `getattr`, etc
    if unravel_attr_access_calls and basename in PYTHON_ATTR_ACCESS_BUILTINS:
        obj, attr = get_python_attr_access_fn_obj_attr_pair(basename, node)
        return basename, f"{obj}.{attr}"

    return basename, f"{lhs_name}()"


def __ast_compound_name(
    node: ast.Attribute | ast.Starred | ast.Subscript,
    *,
    safe: bool = True,
) -> tuple[Identifier, Identifier]:
    basename, lhs_name = names_of(node.value, safe=safe)

    if isinstance(node, ast.Attribute):
        return basename, f"{lhs_name}.{node.attr}"

    if isinstance(node, ast.Subscript):
        return basename, f"{lhs_name}[]"

    if isinstance(node, ast.Starred):
        return basename, f"*{lhs_name}"

    raise NotImplementedError


def __specific_name_error(node: ast.expr) -> type[TypeError]:
    # Give a specific error if possible
    if isinstance(node, ast.UnaryOp):
        return error.RattrUnaryOpInNameable

    if isinstance(node, ast.BinOp):
        return error.RattrBinOpInNameable

    if isinstance(node, ast.Constant):
        return error.RattrConstantInNameable

    if isinstance(node, AstLiterals):
        return error.RattrLiteralInNameable

    if isinstance(node, AstComprehensions):
        return error.RattrComprehensionInNameable

    # We could not be specific :(
    return TypeError
