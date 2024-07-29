"""Annotations to be imported for use by Rattr analysed code."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any, TypeVar, overload

    from rattr.analyser.types import (
        KeywordArgumentName,
        LocalIdentifier,
        PositionalArgumentName,
        TargetName,
    )
    from rattr.ast.types import Identifier
    from rattr.versioning.typing import ParamSpec

    P = ParamSpec("P")
    R = TypeVar("R")

    T = TypeVar("T")


def noop(x: T, /) -> T:
    return x


if TYPE_CHECKING:

    @overload
    def rattr_ignore() -> Callable[[Callable[P, R]], Callable[P, R]]:
        ...

    @overload
    def rattr_ignore(optional_target: Callable[P, R], /) -> Callable[P, R]:
        ...


def rattr_ignore(*optional_target: Callable[P, R]) -> Any:
    """Mark the given function as ignored by rattr."""
    if optional_target:
        if len(optional_target) != 1:
            raise ValueError("rattr_ignore expects exactly one target")

        return optional_target[0]

    return noop


def rattr_results(
    *,
    gets: set[Identifier] | None = None,
    sets: set[Identifier] | None = None,
    dels: set[Identifier] | None = None,
    calls: list[
        tuple[
            TargetName,
            tuple[
                list[PositionalArgumentName],
                dict[KeywordArgumentName, LocalIdentifier],
            ],
        ]
    ]
    | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Explicitly provide the expected rattr results for a function.

    Note that when results are explicitly given rattr will take these as true and will
    not analyse the function body in any way.

    Note also that `Identifier`, `TargetName`, `PositionalArgumentName`,
    `KeywordArgumentName`, and `LocalIdentifier` are all type aliases for `str`.
    """

    return noop
