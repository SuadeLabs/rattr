from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from rattr.models.ir import FileIr
from rattr.models.symbol import (
    Call,
    CallArguments,
    CallInterface,
    Class,
    Func,
    Import,
    Name,
)
from rattr.results._types import IrEnvironment

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests.shared import MakeRootContextFn, StateFn


@pytest.fixture(autouse=True)
def __set_current_file(state: StateFn) -> Iterator[None]:
    with state(current_file=Path("my_example_target.py")):
        yield


@pytest.fixture()
def example_file_ir_a(make_root_context: MakeRootContextFn) -> FileIr:
    fn_a = Func(name="fn_a", interface=CallInterface())
    fn_b = Func(name="fn_b", interface=CallInterface())
    cls_a = Class(name="ClassA", interface=CallInterface(args=("self", "arg")))

    math_dot_sin = Import("sin", "math.sin")

    fn_a_ir = {
        "sets": {Name("a"), Name("b.attr", "b")},
        "gets": {Name("c")},
        "dels": set(),
        "calls": set(),
    }
    fn_b_ir = {
        "sets": set(),
        "gets": set(),
        "dels": {Name("a")},
        "calls": set(),
    }
    cls_a_ir = {
        "sets": {Name("self.field", "self")},
        "gets": {Name("arg.attr", "arg")},
        "dels": set(),
        "calls": set(),
    }

    file_ir = FileIr(
        context=make_root_context(
            symbols=[
                math_dot_sin,
                fn_a,
                fn_b,
                cls_a,
            ],
            include_root_symbols=False,
        ),
        file_ir={
            fn_a: fn_a_ir,
            fn_b: fn_b_ir,
            cls_a: cls_a_ir,
        },
    )

    return file_ir


@pytest.fixture()
def example_environment_a(example_file_ir_a: FileIr) -> IrEnvironment:
    return IrEnvironment(target_ir=example_file_ir_a, import_irs={})


@pytest.fixture()
def example_file_ir_b(make_root_context: MakeRootContextFn) -> FileIr:
    fn_a = Func(name="fn_a", interface=CallInterface(args=("a",)))
    fn_b = Func(name="fn_b", interface=CallInterface(args=("b",)))
    fn_c = Func(name="fn_c", interface=CallInterface(args=("c",)))
    fn_d = Func(name="fn_d", interface=CallInterface(args=("d",)))

    fn_b_call = Call(name="fn_b", args=CallArguments(args=("a",)), target=fn_b)
    fn_c_call = Call(name="fn_c", args=CallArguments(args=("b",)), target=fn_c)
    fn_d_call = Call(name="fn_d", args=CallArguments(args=("b",)), target=fn_d)

    fn_a_ir = {
        "sets": {Name("a")},
        "gets": set(),
        "dels": set(),
        "calls": {fn_b_call},
    }
    fn_b_ir = {
        "sets": {Name("b")},
        "gets": set(),
        "dels": set(),
        "calls": {fn_c_call, fn_d_call},
    }
    fn_c_ir = {
        "sets": {Name("c")},
        "gets": set(),
        "dels": set(),
        "calls": set(),
    }
    fn_d_ir = {
        "sets": {Name("d")},
        "gets": set(),
        "dels": set(),
        "calls": set(),
    }

    file_ir = FileIr(
        context=make_root_context(
            symbols=[
                fn_a,
                fn_b,
                fn_c,
                fn_d,
            ],
            include_root_symbols=False,
        ),
        file_ir={
            fn_a: fn_a_ir,
            fn_b: fn_b_ir,
            fn_c: fn_c_ir,
            fn_d: fn_d_ir,
        },
    )

    return file_ir


@pytest.fixture()
def example_environment_b(example_file_ir_b: FileIr) -> IrEnvironment:
    return IrEnvironment(target_ir=example_file_ir_b, import_irs={})


@pytest.fixture()
def example_file_ir_c(make_root_context: MakeRootContextFn) -> FileIr:
    fn_a = Func(name="fn_a", interface=CallInterface(args=("a",)))
    fn_b = Func(name="fn_b", interface=CallInterface(args=("b",)))

    fn_a_call = Call(name="fn_b", args=CallArguments(args=("a",)), target=fn_b)
    some_undefined_func_call = Call(
        name="some_undefined_func",
        args=CallArguments(args=()),
    )
    some_other_undefined_func_call = Call(
        name="some_other_undefined_func",
        args=CallArguments(args=()),
    )

    fn_a_ir = {
        "sets": {Name("a")},
        "gets": set(),
        "dels": set(),
        "calls": {
            fn_a_call,
            some_undefined_func_call,
        },
    }
    fn_b_ir = {
        "sets": {Name("b")},
        "gets": set(),
        "dels": set(),
        "calls": {
            some_other_undefined_func_call,
        },
    }

    file_ir = FileIr(
        context=make_root_context(
            symbols=[
                fn_a,
                fn_b,
            ],
            include_root_symbols=False,
        ),
        file_ir={
            fn_a: fn_a_ir,
            fn_b: fn_b_ir,
        },
    )

    return file_ir


@pytest.fixture()
def example_environment_c(example_file_ir_c: FileIr) -> IrEnvironment:
    return IrEnvironment(target_ir=example_file_ir_c, import_irs={})


@pytest.fixture()
def example_file_ir_d(make_root_context: MakeRootContextFn) -> FileIr:
    fn_a = Func(name="fn_a", interface=CallInterface(args=("a",)))
    os_path_join_call = Call("os.path.join", args=CallArguments(args=()))
    math_max_call = Call("math.max", args=CallArguments(args=()))

    fn_a_ir = {
        "sets": {Name("a")},
        "gets": set(),
        "dels": set(),
        "calls": {
            os_path_join_call,
            math_max_call,
        },
    }

    file_ir = FileIr(
        context=make_root_context(
            symbols=[
                fn_a,
            ],
            include_root_symbols=False,
        ),
        file_ir={
            fn_a: fn_a_ir,
        },
    )

    return file_ir


@pytest.fixture()
def example_environment_d(example_file_ir_d: FileIr) -> IrEnvironment:
    return IrEnvironment(target_ir=example_file_ir_d, import_irs={})


@pytest.fixture()
def example_file_ir_e(make_root_context: MakeRootContextFn) -> FileIr:
    fn_a = Func(name="fn_a", interface=CallInterface(args=("a",)))
    max_call = Call("max", args=CallArguments(args=()))
    enumerate_call = Call("enumerate", args=CallArguments(args=()))

    fn_a_ir = {
        "sets": {Name("a")},
        "gets": set(),
        "dels": set(),
        "calls": {
            max_call,
            enumerate_call,
        },
    }

    file_ir = FileIr(
        context=make_root_context(
            symbols=[
                fn_a,
            ],
            include_root_symbols=False,
        ),
        file_ir={
            fn_a: fn_a_ir,
        },
    )

    return file_ir


@pytest.fixture()
def example_environment_e(example_file_ir_e: FileIr) -> IrEnvironment:
    return IrEnvironment(target_ir=example_file_ir_e, import_irs={})


@pytest.fixture()
def example_file_ir_f(make_root_context: MakeRootContextFn) -> FileIr:
    fn_a = Func(name="fn_a", interface=CallInterface(args=("a",)))
    fn_b = Func(name="fn_b", interface=CallInterface(args=("b",)))
    fn_c = Func(name="fn_c", interface=CallInterface(args=("c",)))

    fn_a_ir = {
        "sets": {Name("a")},
        "gets": set(),
        "dels": set(),
        "calls": {
            Call(name="fn_a", args=CallArguments(args=("a",)), target=fn_a),
            Call(name="fn_b", args=CallArguments(args=("a",)), target=fn_b),
        },
    }
    fn_b_ir = {
        "sets": {Name("b")},
        "gets": set(),
        "dels": set(),
        "calls": {
            Call(name="fn_a", args=CallArguments(args=("b",)), target=fn_a),
            Call(name="fn_c", args=CallArguments(args=("b",)), target=fn_c),
        },
    }
    fn_c_ir = {
        "sets": {Name("b")},
        "gets": set(),
        "dels": set(),
        "calls": {
            Call(name="fn_b", args=CallArguments(args=("c",)), target=fn_b),
        },
    }

    file_ir = FileIr(
        context=make_root_context(
            symbols=[
                fn_a,
                fn_b,
                fn_c,
            ],
            include_root_symbols=False,
        ),
        file_ir={
            fn_a: fn_a_ir,
            fn_b: fn_b_ir,
            fn_c: fn_c_ir,
        },
    )

    return file_ir


@pytest.fixture()
def example_environment_f(example_file_ir_f: FileIr) -> IrEnvironment:
    return IrEnvironment(target_ir=example_file_ir_f, import_irs={})
