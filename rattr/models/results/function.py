from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from rattr.ast.types import Identifier

if TYPE_CHECKING:
    from collections.abc import Iterable


class FunctionResults(TypedDict):
    gets: set[Identifier]
    sets: set[Identifier]
    dels: set[Identifier]
    calls: set[Identifier]

    @classmethod
    def the_empty_results(cls) -> FunctionResults:
        return {"gets": set(), "sets": set(), "dels": set(), "calls": set()}

    @classmethod
    def new(
        cls,
        *,
        gets: Iterable[Identifier] = (),
        sets: Iterable[Identifier] = (),
        dels: Iterable[Identifier] = (),
        calls: Iterable[Identifier] = (),
    ) -> FunctionResults:
        return {
            "gets": set(gets),
            "sets": set(sets),
            "dels": set(dels),
            "calls": set(calls),
        }
