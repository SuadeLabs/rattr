from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

from rattr.extra.functools import deferred_execute_once

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeVar

    T = TypeVar("T")


def test_deferred_execute_once_first_call():
    def identity(x: T, /) -> T:
        return x

    one_shot = deferred_execute_once(identity, "foo")

    assert one_shot() == "foo"


def test_deferred_execute_once_multiple_calls_are_allowed():
    def identity(x: T, /) -> T:
        return x

    one_shot = deferred_execute_once(identity, "foo")

    for _ in range(10):
        assert one_shot() == "foo"


def test_deferred_execute_once_returns_cached_first_value_on_subsequent_calls():
    def make_counter() -> Callable[[], int]:
        i = 0

        def counter() -> int:
            nonlocal i

            i += 1

            return i

        return counter

    # In normal use subsequent calls are different
    counter = make_counter()
    assert counter() == 1
    assert counter() == 2
    assert counter() == 3

    one_shot = deferred_execute_once(make_counter())

    # With `execute_once` we always return the cached first result
    for _ in range(10):
        assert one_shot() == 1


def test_deferred_execute_once_call_count():
    target = mock.Mock(return_value=1)

    one_shot = deferred_execute_once(target)

    for _ in range(10):
        assert one_shot() == 1

    # Even though we call `one_shot` many times, the target fn is called exactly once
    assert target.call_count == 1


def test_deferred_execute_once_passes_args_and_kwargs():
    def thing(a: str, /, b: str, *, c: int) -> tuple[str, str, int]:
        return (a, b, c)

    one_shot = deferred_execute_once(thing, "hi", "there", c=1)

    for _ in range(10):
        assert one_shot() == ("hi", "there", 1)
