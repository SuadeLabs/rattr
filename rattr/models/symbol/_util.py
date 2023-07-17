"""Private util functions."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from rattr import error

if TYPE_CHECKING:
    from typing import Final, NoReturn


_unsupported_feature: Final = "{feature} not supported in function calls"


def arg_name(arg: ast.expr) -> str:
    """Return the safely-evaluated argument name."""
    from rattr.analyser.util import get_fullname  # circular dep.

    if isinstance(arg, ast.Starred):
        error.error(_unsupported_feature.format(feature="iterable unpacking"))

    return get_fullname(arg, safe=True)


def kwarg_name(kwarg: ast.keyword) -> str | NoReturn:
    """Return the safely-evaluated keyword-argument name."""
    from rattr.analyser.util import get_fullname  # circular dep.

    if kwarg.arg is None:
        error.fatal(_unsupported_feature.format(feature="dictionary unpacking"))

    return get_fullname(kwarg.value, safe=True)
