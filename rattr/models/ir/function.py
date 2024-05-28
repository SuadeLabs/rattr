from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from rattr.models.symbol import Call, Name

if TYPE_CHECKING:
    from collections.abc import Iterable


class FunctionIr(TypedDict):
    gets: set[Name]
    sets: set[Name]
    dels: set[Name]
    calls: set[Call]

    @classmethod
    def the_empty_ir(cls) -> FunctionIr:
        return {"gets": set(), "sets": set(), "dels": set(), "calls": set()}

    @classmethod
    def new(
        cls,
        *,
        gets: Iterable[Name] = (),
        sets: Iterable[Name] = (),
        dels: Iterable[Name] = (),
        calls: Iterable[Call] = (),
    ) -> FunctionIr:
        return {
            "gets": set(gets),
            "sets": set(sets),
            "dels": set(dels),
            "calls": set(calls),
        }
