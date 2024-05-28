from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rattr.ast.types import Identifier


def gen_import_from_stmt(module: Identifier, target: Identifier) -> str:
    if not module.isidentifier():
        raise ValueError(f"{module!r} is not a valid identifier")

    if target != "*" and not target.isidentifier():
        raise ValueError(f"{target!r} is not a valid identifier")

    return f"from {module} import {target}"
