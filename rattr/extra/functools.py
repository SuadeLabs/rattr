from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeVar

    from rattr.versioning.typing import ParamSpec

    P = ParamSpec("P")
    R = TypeVar("R")


def deferred_execute_once(
    op: Callable[P, R],
    /,
    *args: P.args,
    **kwargs: P.kwargs,
) -> Callable[[], R]:
    result = None

    def factory() -> R:
        nonlocal result

        if result is None:
            result = op(*args, **kwargs)

        return result

    return factory
