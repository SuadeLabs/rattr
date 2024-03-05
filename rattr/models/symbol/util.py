from __future__ import annotations

from rattr.models.symbol._util import (  # noqa: F401
    PYTHON_BUILTINS_LOCATION,
    arg_name,
    kwarg_name,
)


def with_call_brackets(call: str) -> str:
    """Return the given string with call brackets added if absent.

    >>> without_call_brackets("keep_my_call_brackets()")
    "keep_my_call_brackets()"
    >>> without_call_brackets("i_dont_have_call_brackets")
    "i_dont_have_call_brackets()"
    """
    if not call.endswith("()"):
        return f"{call}()"

    return call


def without_call_brackets(call: str) -> str:
    """Return the given string with call brackets removed if present.

    >>> without_call_brackets("remove_my_call_brackets()")
    "remove_my_call_brackets"
    >>> without_call_brackets("i_dont_have_call_brackets")
    "i_dont_have_call_brackets"
    """
    while call.endswith("()"):
        call = call.removesuffix("()")
    return call


def get_basename_from_name(name: str) -> str:
    """Return the basename for the given name.

    >>> get_basename_from_name("my_var")
    "my_var"

    >>> get_basename_from_name("my_var.attr")
    "my_var"

    >>> get_basename_from_name("*my_var.attr.method()")
    "my_var"
    """
    return without_call_brackets(name).replace("*", "").split(".", maxsplit=1)[0]
