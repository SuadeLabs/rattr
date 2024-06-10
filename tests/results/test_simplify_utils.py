from __future__ import annotations

import pytest

from rattr.models.ir import FunctionIr
from rattr.models.symbol import Call, CallArguments, CallInterface, Func, Name
from rattr.results._simplify_utils import (
    construct_call_swaps,
    unbind_ir_with_call_swaps,
    unbind_name,
)
from tests.shared import match_output


@pytest.mark.parametrize(
    "name, basename, new_basename, resultant",
    [
        # Identity
        ("foo", "foo", "foo", "foo"),
        ("*foo", "foo", "foo", "*foo"),
        ("foo[]", "foo", "foo", "foo[]"),
        ("*foo[]", "foo", "foo", "*foo[]"),
        # Simple substitution
        ("foo", "foo", "bar", "bar"),
        ("*foo", "foo", "bar", "*bar"),
        ("foo[]", "foo", "bar", "bar[]"),
        ("*foo[]", "foo", "bar", "*bar[]"),
        # Complex identity
        (
            "comp.attr.m().res_attr[].item",
            "comp",
            "comp",
            "comp.attr.m().res_attr[].item",
        ),
        (
            "*comp.attr.m().res_attr[].item",
            "comp",
            "comp",
            "*comp.attr.m().res_attr[].item",
        ),
        (
            "comp.attr.m().res_attr[].item[]",
            "comp",
            "comp",
            "comp.attr.m().res_attr[].item[]",
        ),
        (
            "*comp.attr.m().res_attr[].item[]",
            "comp",
            "comp",
            "*comp.attr.m().res_attr[].item[]",
        ),
        # Complex substitution
        (
            "comp.attr.m().res_attr[].item",
            "comp",
            "bar",
            "bar.attr.m().res_attr[].item",
        ),
        (
            "*comp.attr.m().res_attr[].item",
            "comp",
            "bar",
            "*bar.attr.m().res_attr[].item",
        ),
        (
            "comp.attr.m().res_attr[].item[]",
            "comp",
            "bar",
            "bar.attr.m().res_attr[].item[]",
        ),
        (
            "*comp.attr.m().res_attr[].item[]",
            "comp",
            "bar",
            "*bar.attr.m().res_attr[].item[]",
        ),
    ],
)
def test_unbind_name(name: str, basename: str, new_basename: str, resultant: str):
    lhs = Name(name, basename)
    rhs = Name(resultant, new_basename)
    assert unbind_name(lhs, new_basename) == rhs


def test_unbind_ir_with_call_swaps_empty_ir_with_no_swaps():
    assert (
        unbind_ir_with_call_swaps(FunctionIr.the_empty_ir(), {})
        == FunctionIr.the_empty_ir()
    )


def test_unbind_ir_with_call_swaps_empty_ir_with_swaps():
    assert (
        unbind_ir_with_call_swaps(FunctionIr.the_empty_ir(), {"a": "b"})
        == FunctionIr.the_empty_ir()
    )


@pytest.fixture()
def example_func_ir_a():
    return {
        "sets": {
            Name("a"),
            Name("a.attr", "a"),
        },
        "gets": {
            Name("arg"),
            Name("arg.mth().res_attr[].value", "arg"),
        },
        "dels": {
            Name("bob"),
            Name("*dob", "dob"),
        },
        "calls": {
            Call(name="callee()", args=CallArguments(), target=None),
        },
    }


def test_unbind_ir_with_call_swaps_func_with_no_swaps(example_func_ir_a: FunctionIr):
    assert unbind_ir_with_call_swaps(example_func_ir_a, {}) == example_func_ir_a


def test_unbind_ir_with_call_swaps_func_with_simple_swap_single(
    example_func_ir_a: FunctionIr,
):
    swap = {"a": "b"}
    expected = {
        "sets": {
            Name("b"),
            Name("b.attr", "b"),
        },
        "gets": {
            Name("arg"),
            Name("arg.mth().res_attr[].value", "arg"),
        },
        "dels": {
            Name("bob"),
            Name("*dob", "dob"),
        },
        "calls": {
            Call(name="callee()", args=CallArguments(), target=None),
        },
    }
    assert unbind_ir_with_call_swaps(example_func_ir_a, swap) == expected


def test_unbind_ir_with_call_swaps_func_with_simple_swaps(
    example_func_ir_a: FunctionIr,
):
    swap = {
        "arg": "barg",
        "bob": "bobby",
    }
    expected = {
        "sets": {
            Name("a"),
            Name("a.attr", "a"),
        },
        "gets": {
            Name("barg"),
            Name("barg.mth().res_attr[].value", "barg"),
        },
        "dels": {
            Name("bobby"),
            Name("*dob", "dob"),
        },
        "calls": {
            Call(name="callee()", args=CallArguments(), target=None),
        },
    }
    assert unbind_ir_with_call_swaps(example_func_ir_a, swap) == expected


def test_unbind_ir_with_call_swaps_func_with_mixed_swaps(
    example_func_ir_a: FunctionIr,
):
    # Mixed insofar as some are relevant and some are irrelevant
    swap = {
        "dob": "dib",
        "xyz": "zyx",
    }
    expected = {
        "sets": {
            Name("a"),
            Name("a.attr", "a"),
        },
        "gets": {
            Name("arg"),
            Name("arg.mth().res_attr[].value", "arg"),
        },
        "dels": {
            Name("bob"),
            Name("*dib", "dib"),
        },
        "calls": {
            Call(name="callee()", args=CallArguments(), target=None),
        },
    }
    assert unbind_ir_with_call_swaps(example_func_ir_a, swap) == expected


def test_unbind_ir_with_call_swaps_regression():
    func_ir = FunctionIr.new(sets={Name(name="arg_b.set_in_fn_b", basename="arg_b")})
    expected = FunctionIr.new(sets={Name(name="arg.set_in_fn_b", basename="arg")})
    assert unbind_ir_with_call_swaps(func_ir, {"arg_b": "arg"}) == expected


@pytest.mark.parametrize(
    "interface, arguments, expected, expected_stderr",
    testcases := [
        # Empty
        (
            CallInterface(),
            CallArguments(),
            {},
            [],
        ),
        # Not enough args to satisfy positional arguments
        (
            CallInterface(posonlyargs=("a",)),
            CallArguments(args=()),
            {},
            [
                "call to 'fn' expected 1 posonlyargs but only received 0 "
                "positional arguments",
            ],
        ),
        (
            CallInterface(posonlyargs=("a",)),
            CallArguments(args=(), kwargs={"a": "fail?"}),
            {},
            [
                "call to 'fn' expected 1 posonlyargs but only received 0 "
                "positional arguments",
            ],
        ),
        # posonlyargs
        (
            CallInterface(args=("a", "b")),
            CallArguments(args=("a", "b")),
            {"a": "a", "b": "b"},
            [],
        ),
        (
            CallInterface(posonlyargs=("a_interface", "b_interface")),
            CallArguments(args=("a_call", "b_call"), kwargs={}),
            {"a_interface": "a_call", "b_interface": "b_call"},
            [],
        ),
        # positional args
        (
            CallInterface(posonlyargs=("a", "b"), args=("c", "d")),
            CallArguments(args=("A", "B", "C"), kwargs={"d": "D"}),
            {"a": "A", "b": "B", "c": "C", "d": "D"},
            [],
        ),
        (
            CallInterface(posonlyargs=("a", "b"), args=("c", "d")),
            CallArguments(args=("A", "B", "C"), kwargs={"d": "D", "e": "E"}),
            {"a": "A", "b": "B", "c": "C", "d": "D"},
            [
                "call to 'fn' received unexpected keyword arguments: ['e']",
            ],
        ),
        # positional args w/ vararg
        # ... with empty `rem`
        (
            CallInterface(posonlyargs=("a",), args=("b", "c"), vararg="rem"),
            CallArguments(args=("A", "B", "C"), kwargs={}),
            {"a": "A", "b": "B", "c": "C", "rem": "@Tuple"},
            [],
        ),
        # ... with non-empty `rem`
        (
            CallInterface(posonlyargs=("a",), args=("b", "c"), vararg="rem"),
            CallArguments(args=("A", "B", "C", "D", "E", "F"), kwargs={}),
            {"a": "A", "b": "B", "c": "C", "rem": "@Tuple"},
            [],
        ),
        # keyword args
        (
            CallInterface(args=("a", "b", "c")),
            CallArguments(args=("A",), kwargs={"c": "C", "b": "B"}),
            {"a": "A", "b": "B", "c": "C"},
            [],
        ),
        # ... with a vararg
        (
            CallInterface(args=("a", "b", "c"), vararg="rem"),
            CallArguments(args=("A", "B"), kwargs={"c": "C", "b": "B"}),
            {"a": "A", "b": "B", "c": "C", "rem": "@Tuple"},
            [
                "call to 'fn' received the arguments ['b'] by position and name",
            ],
        ),
        # kwonlyargs
        (
            CallInterface(kwonlyargs=("a", "b", "c")),
            CallArguments(args=("A", "B"), kwargs={"c": "C"}),
            {"c": "C"},
            [
                "call to 'fn' received too many positional arguments",
            ],
        ),
        (
            CallInterface(kwonlyargs=("a", "b", "c")),
            CallArguments(args=(), kwargs={"c": "C"}),
            {"c": "C"},
            [],
        ),
        (
            CallInterface(kwonlyargs=("a", "b", "c")),
            CallArguments(args=(), kwargs={"a": "A", "c": "C", "b": "B"}),
            {"a": "A", "b": "B", "c": "C"},
            [],
        ),
        # keyword args
        (
            CallInterface(args=("a",), vararg="rem", kwonlyargs=("b", "c")),
            CallArguments(args=("A", "extra"), kwargs={"c": "C", "b": "B"}),
            {"a": "A", "b": "B", "c": "C", "rem": "@Tuple"},
            [],
        ),
        # ... with assumed default
        (
            CallInterface(args=("a", "b", "c", "d", "e")),
            CallArguments(args=("not_a", "not_b"), kwargs={"d": "not_d", "c": "not_c"}),
            {"a": "not_a", "b": "not_b", "c": "not_c", "d": "not_d"},
            [],
        ),
        # kwarg
        (
            CallInterface(
                args=("a",),
                vararg="rem",
                kwonlyargs=("b", "c"),
                kwarg="kwargs",
            ),
            CallArguments(args=("A", "extra"), kwargs={"c": "C", "b": "B"}),
            {"a": "A", "b": "B", "c": "C", "rem": "@Tuple"},
            [],
        ),
        (
            CallInterface(
                args=("a",),
                vararg="rem",
                kwonlyargs=("b", "c"),
                kwarg="kwargs",
            ),
            CallArguments(
                args=("A", "extra"),
                kwargs={
                    "c": "C",
                    "b": "B",
                    "kw": "a_kwarg",
                    "kw2": "another_kwarg",
                },
            ),
            {"a": "A", "b": "B", "c": "C", "rem": "@Tuple", "kwargs": "@Dict"},
            [],
        ),
        # Complex examples
        (
            CallInterface(
                posonlyargs=("a", "b"),
                args=("c", "d"),
                vararg="args",
                kwonlyargs=("e",),
                kwarg="kwarg",
            ),
            CallArguments(args=(), kwargs={}),
            {},
            [
                "call to 'fn' expected 2 posonlyargs but only received 0 "
                "positional arguments",
            ],
        ),
        (
            CallInterface(
                posonlyargs=("a", "b"),
                args=("c", "d"),
                vararg="args",
                kwonlyargs=("e",),
                kwarg="kwarg",
            ),
            CallArguments(args=("A", "B", "C", "D", "extra"), kwargs={"e": "E"}),
            {"a": "A", "b": "B", "c": "C", "d": "D", "args": "@Tuple", "e": "E"},
            [],
        ),
        (
            CallInterface(
                posonlyargs=("a", "b"),
                args=("c", "d"),
                vararg="args",
                kwonlyargs=("e",),
                kwarg="kwarg",
            ),
            CallArguments(args=("A", "B", "C", "D", "extra"), kwargs={}),
            {"a": "A", "b": "B", "c": "C", "d": "D", "args": "@Tuple"},
            [],
        ),
        (
            CallInterface(
                posonlyargs=("a", "b"),
                args=("c", "d"),
                vararg="args",
                kwonlyargs=("e",),
                kwarg="kwarg",
            ),
            CallArguments(args=("A", "B", "C"), kwargs={"e": "E", "d": "D"}),
            {"a": "A", "b": "B", "c": "C", "d": "D", "args": "@Tuple", "e": "E"},
            [],
        ),
        # Some errors
        (
            CallInterface(args=("a",)),
            CallArguments(args=("not_a",), kwargs={"a": "not_a"}),
            {"a": "not_a"},
            ["call to 'fn' received the arguments ['a'] by position and name"],
        ),
        (
            CallInterface(args=("a", "b")),
            CallArguments(args=(), kwargs={"c": "no_match", "d": "no_match"}),
            {},
            ["call to 'fn' received unexpected keyword arguments: ['c', 'd']"],
        ),
    ],
    ids=[i for i, _ in enumerate(testcases)],
)
def test_construct_swap(
    interface: CallInterface,
    arguments: CallArguments,
    expected: dict[str, str],
    expected_stderr: list[str],
    capfd: pytest.CaptureFixture[str],
):
    fn_def = Func(name="fn", interface=interface)
    fn_call = Call(name="fn", args=arguments)

    assert construct_call_swaps(fn_def, fn_call) == expected

    _, stderr = capfd.readouterr()
    assert match_output(stderr, expected_stderr)
