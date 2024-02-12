from __future__ import annotations

from typing import TypedDict

from rattr.ast.types import Identifier


class FunctionResults(TypedDict):
    gets: set[Identifier]
    sets: set[Identifier]
    dels: set[Identifier]
    calls: set[Identifier]
