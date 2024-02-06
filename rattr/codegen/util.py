from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _ast import _Identifier


def gen_import_from_stmt(module: _Identifier, target: _Identifier) -> str:
    if not module.isidentifier():
        raise ValueError(f"{module!r} is not a valid identifier")

    if not target.isidentifier():
        raise ValueError(f"{target!r} is not a valid identifier")

    return f"from {module} import {target}"
