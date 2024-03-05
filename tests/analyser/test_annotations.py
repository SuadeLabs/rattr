from __future__ import annotations

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


def test_rattr_results_is_identity():
    @rattr_results(gets={"a", "b"})
    def my_test_fn(a: str) -> bool:
        return a == "hello"

    assert not my_test_fn("hi")
    assert my_test_fn("hello")
