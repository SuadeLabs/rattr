from __future__ import annotations

import pytest

from rattr.analyser.annotations import rattr_ignore, rattr_results


def test_rattr_ignore_is_identity():
    @rattr_ignore()
    def my_test_fn(a: str) -> bool:
        return a == "hello"

    assert not my_test_fn("hi")
    assert my_test_fn("hello")


def test_rattr_ignore_without_call_brackets_is_identity():
    @rattr_ignore
    def my_test_fn(a: str) -> bool:
        return a == "hello"

    assert not my_test_fn("hi")
    assert my_test_fn("hello")


def test_rattr_ignore_explicit_target_valid():
    def my_test_fn(a: str) -> bool:
        return a == "hello"

    my_test_fn = rattr_ignore(my_test_fn)

    assert not my_test_fn("hi")
    assert my_test_fn("hello")


def test_rattr_ignore_explicit_target_invalid():
    def my_test_fn(a: str) -> bool:
        return a == "hello"

    # This will be eq. to:
    #   my_test_fn = rattr_ignore(my_test_fn)
    #   my_second_target = my_test_fn(my_second_target)
    # Which is obviously invalid
    # This is a type error that should be picked up, and it will fail at runtime, but it
    # does not fail at the point of decorator use.
    @rattr_ignore(my_test_fn)  # type: ignore[reportArgumentType]
    def my_second_target(a: str) -> bool:
        return a != "hello"

    with pytest.raises(TypeError, match="'bool' object is not callable"):
        assert not my_second_target("hi")  # type: ignore[reportCallIssue]
    with pytest.raises(TypeError, match="'bool' object is not callable"):
        assert my_second_target("hello")  # type: ignore[reportCallIssue]


def test_rattr_results_is_identity():
    @rattr_results(gets={"a", "b"})
    def my_test_fn(a: str) -> bool:
        return a == "hello"

    assert not my_test_fn("hi")
    assert my_test_fn("hello")
