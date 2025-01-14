from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeVar

    from rattr.versioning.typing import ParamSpec

    _P = ParamSpec("_P")
    _R = TypeVar("_R")


def deferred_execute_once(
    op: Callable[_P, _R],
    /,
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> Callable[[], _R]:
    result = None

    def factory() -> _R:
        nonlocal result

        if result is None:
            result = op(*args, **kwargs)

        return result

    return factory
