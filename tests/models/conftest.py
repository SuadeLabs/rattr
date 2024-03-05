from __future__ import annotations

from pathlib import Path

import pytest

from rattr.models.symbol import (
    AnyCallInterface,
    Builtin,
    Call,
    CallArguments,
    Class,
    Func,
    Import,
    Name,
)


@pytest.fixture()
def test_file() -> Path:
    return Path("test.py")


@pytest.fixture(autouse=True)
def __set_current_file(state, test_file):
    # Many symbols automatically derive a location
    # The derivation will error if the state's file is not set
    # Se just set it universally for all symbol tests.
    with state(current_file=test_file):
        yield


@pytest.fixture()
def simple_name() -> Name:
    return Name("jeffery")


@pytest.fixture()
def simple_builtin() -> Builtin:
    return Builtin("some_builtin_func")


@pytest.fixture()
def simple_import() -> Import:
    return Import("some_lib_func")


@pytest.fixture()
def simple_func() -> Func:
    return Func("some_user_func", interface=AnyCallInterface())


@pytest.fixture()
def simple_class() -> Class:
    return Class("SomeClass", interface=AnyCallInterface())


@pytest.fixture()
def simple_call() -> Call:
    return Call("my_func", args=CallArguments())
