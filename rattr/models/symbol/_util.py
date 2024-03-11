"""Private util functions."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from rattr import error

if TYPE_CHECKING:
    from typing import Final, NoReturn


_feature_not_supported: Final = "{feature} not supported in function calls"

PYTHON_BUILTINS_LOCATION: Final = "built-in"
"""Python's built-in function location.

This is the module spec origin for several stdlib modules.
"""


def arg_name(arg: ast.expr, *, culprit: ast.Call | None = None) -> str:
    """Return the safely-evaluated argument name."""
    from rattr.analyser.util import get_fullname  # circular dep.

    if isinstance(arg, ast.Starred):
        error.error(
            _feature_not_supported.format(feature="iterable unpacking"),
            culprit=culprit,
        )

    return get_fullname(arg, safe=True)


def kwarg_name(
    kwarg: ast.keyword,
    *,
    culprit: ast.Call | None = None,
) -> str | NoReturn:
    """Return the safely-evaluated keyword-argument name."""
    from rattr.analyser.util import get_fullname  # circular dep.

    if kwarg.arg is None:
        error.fatal(
            _feature_not_supported.format(feature="dictionary unpacking"),
            culprit=culprit,
        )

    return get_fullname(kwarg.value, safe=True)
