"""Annotations to be imported for use by Rattr analysed code."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeVar

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


def rattr_ignore(*optional_target: Callable[P, R]) -> Callable[P, R]:
    """Mark the given function as ignored by rattr."""
    if optional_target:
        if len(optional_target) != 1:
            raise ValueError("rattr_ignore expects exactly one target")

        return optional_target[0]

    def _inner(target: Callable[P, R]) -> Callable[P, R]:
        return target

    return _inner


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
) -> Callable[P, R]:
    """Explicitly provide the expected rattr results for a function.

    Note that when results are explicitly given rattr will take these as true and will
    not analyse the function body in any way.

    Note also that `Identifier`, `TargetName`, `PositionalArgumentName`,
    `KeywordArgumentName`, and `LocalIdentifier` are all type aliases for `str`.
    """

    def _inner(f: Callable[P, R]) -> Callable[P, R]:
        return f

    return _inner
