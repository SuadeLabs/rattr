from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from rattr.models.symbol import Call, CallArguments, CallInterface, Class, Func
from rattr.results._types import IrCall, IrCallTreeNode, IrTarget
from rattr.results.util import make_target_ir_call_tree
from tests.shared import match_output

if TYPE_CHECKING:
    from rattr.results._types import IrEnvironment


def test_make_target_ir_call_tree_a(
    example_environment_a: IrEnvironment,
):
    # Each function in example_environment_a has no calls, so each call tree is only the
    # root node
    file_ir = example_environment_a.target_ir
    symbols = (
        Func(name="fn_a", interface=CallInterface()),
        Func(name="fn_b", interface=CallInterface()),
        Class(name="ClassA", interface=CallInterface(args=("self", "arg"))),
    )
    for symbol in symbols:
        target = IrTarget(symbol=symbol, ir=file_ir[symbol])
        expected = IrCallTreeNode(
            target=target,
            edge_in=None,
            edges_out=[],
            children=[],
        )
        assert (
            make_target_ir_call_tree(target, environment=example_environment_a)
            == expected
        )


def test_make_target_ir_call_tree_b(
    example_environment_b: IrEnvironment,
):
    file_ir = example_environment_b.target_ir

    fn_d = Func(name="fn_d", interface=CallInterface(args=("d",)))
    fn_d_target = IrTarget(symbol=fn_d, ir=file_ir[fn_d])
    fn_d_actual = make_target_ir_call_tree(
        fn_d_target,
        environment=example_environment_b,
    )
    fn_d_expected = IrCallTreeNode(
        target=fn_d_target,
        edge_in=None,
        edges_out=[],
        children=[],
    )
    assert fn_d_actual == fn_d_expected

    fn_c = Func(name="fn_c", interface=CallInterface(args=("c",)))
    fn_c_target = IrTarget(symbol=fn_c, ir=file_ir[fn_c])
    fn_c_actual = make_target_ir_call_tree(
        fn_c_target,
        environment=example_environment_b,
    )
    fn_c_expected = IrCallTreeNode(
        target=fn_c_target,
        edge_in=None,
        edges_out=[],
        children=[],
    )
    assert fn_c_actual == fn_c_expected

    fn_b = Func(name="fn_b", interface=CallInterface(args=("b",)))
    fn_b_target = IrTarget(symbol=fn_b, ir=file_ir[fn_b])
    fn_b_actual = make_target_ir_call_tree(
        fn_b_target,
        environment=example_environment_b,
    )
    fn_b_expected = IrCallTreeNode(
        target=fn_b_target,
        edge_in=None,
        edges_out=[
            fn_b_to_fn_c_call := IrCall(
                caller=fn_b,
                symbol=Call(name="fn_c", args=CallArguments(args=("b",)), target=fn_c),
            ),
            fn_b_to_fn_d_call := IrCall(
                caller=fn_b,
                symbol=Call(name="fn_d", args=CallArguments(args=("b",)), target=fn_d),
            ),
        ],
        children=[
            IrCallTreeNode(
                target=fn_c_expected.target,
                edge_in=fn_b_to_fn_c_call,
                edges_out=fn_c_expected.edges_out,
                children=fn_c_expected.children,
            ),
            IrCallTreeNode(
                target=fn_d_expected.target,
                edge_in=fn_b_to_fn_d_call,
                edges_out=fn_d_expected.edges_out,
                children=fn_d_expected.children,
            ),
        ],
    )
    assert fn_b_actual == fn_b_expected

    fn_a = Func(name="fn_a", interface=CallInterface(args=("a",)))
    fn_a_target = IrTarget(symbol=fn_a, ir=file_ir[fn_a])
    fn_a_actual = make_target_ir_call_tree(
        fn_a_target,
        environment=example_environment_b,
    )
    fn_a_expected = IrCallTreeNode(
        target=fn_a_target,
        edge_in=None,
        edges_out=[
            fn_a_to_fn_b_call := IrCall(
                caller=fn_a,
                symbol=Call(name="fn_b", args=CallArguments(args=("a",)), target=fn_b),
            ),
        ],
        children=[
            IrCallTreeNode(
                target=fn_b_expected.target,
                edge_in=fn_a_to_fn_b_call,
                edges_out=fn_b_expected.edges_out,
                children=fn_b_expected.children,
            ),
        ],
    )
    assert fn_a_actual == fn_a_expected


def test_make_target_ir_call_tree_c(
    example_environment_c: IrEnvironment,
    capfd: pytest.CaptureFixture[str],
):
    file_ir = example_environment_c.target_ir

    fn_b = Func(name="fn_b", interface=CallInterface(args=("b",)))
    fn_b_target = IrTarget(symbol=fn_b, ir=file_ir[fn_b])
    fn_b_actual = make_target_ir_call_tree(
        fn_b_target,
        environment=example_environment_c,
    )
    fn_b_expected = IrCallTreeNode(
        target=fn_b_target,
        edge_in=None,
        edges_out=[
            IrCall(
                caller=fn_b,
                symbol=Call(
                    name="some_other_undefined_func",
                    args=CallArguments(args=()),
                ),
            ),
        ],
        children=[],
    )
    assert fn_b_actual == fn_b_expected

    fn_a = Func(name="fn_a", interface=CallInterface(args=("a",)))
    fn_a_target = IrTarget(symbol=fn_a, ir=file_ir[fn_a])
    fn_a_actual = make_target_ir_call_tree(
        fn_a_target,
        environment=example_environment_c,
    )
    fn_a_expected = IrCallTreeNode(
        target=fn_a_target,
        edge_in=None,
        edges_out=[
            fn_a_to_fn_b_call := IrCall(
                caller=fn_a,
                symbol=Call(name="fn_b", args=CallArguments(args=("a",)), target=fn_b),
            ),
            IrCall(
                caller=fn_a,
                symbol=Call(
                    name="some_undefined_func",
                    args=CallArguments(args=()),
                ),
            ),
        ],
        children=[
            IrCallTreeNode(
                target=fn_b_expected.target,
                edge_in=fn_a_to_fn_b_call,
                edges_out=fn_b_expected.edges_out,
                children=fn_b_expected.children,
            ),
        ],
    )
    assert fn_a_actual == fn_a_expected

    _, stderr = capfd.readouterr()
    assert match_output(stderr, [])


def test_make_target_ir_call_tree_d(
    example_environment_d: IrEnvironment,
    capfd: pytest.CaptureFixture[str],
):
    file_ir = example_environment_d.target_ir

    fn_a = Func(name="fn_a", interface=CallInterface(args=("a",)))
    fn_a_target = IrTarget(symbol=fn_a, ir=file_ir[fn_a])
    fn_a_actual = make_target_ir_call_tree(
        fn_a_target,
        environment=example_environment_d,
    )
    fn_a_expected = IrCallTreeNode(
        target=fn_a_target,
        edge_in=None,
        edges_out=[
            IrCall(
                caller=fn_a,
                symbol=Call("math.max", args=CallArguments(args=())),
            ),
            IrCall(
                caller=fn_a,
                symbol=Call("os.path.join", args=CallArguments(args=())),
            ),
        ],
        children=[],
    )
    assert fn_a_actual == fn_a_expected

    _, stderr = capfd.readouterr()
    assert match_output(stderr, [])


def test_make_target_ir_call_tree_e(
    example_environment_e: IrEnvironment,
    capfd: pytest.CaptureFixture[str],
):
    file_ir = example_environment_e.target_ir

    fn_a = Func(name="fn_a", interface=CallInterface(args=("a",)))
    fn_a_target = IrTarget(symbol=fn_a, ir=file_ir[fn_a])
    fn_a_actual = make_target_ir_call_tree(
        fn_a_target,
        environment=example_environment_e,
    )
    fn_a_expected = IrCallTreeNode(
        target=fn_a_target,
        edge_in=None,
        edges_out=[
            IrCall(
                caller=fn_a,
                symbol=Call("enumerate", args=CallArguments(args=())),
            ),
            IrCall(
                caller=fn_a,
                symbol=Call("max", args=CallArguments(args=())),
            ),
        ],
        children=[],
    )
    assert fn_a_actual == fn_a_expected

    _, stderr = capfd.readouterr()
    assert match_output(stderr, [])


def test_make_target_ir_call_tree_f(
    example_environment_f: IrEnvironment,
    capfd: pytest.CaptureFixture[str],
):
    # This test environment has lots of direct and indirect recursion, which is handled
    # correctly with the cycles removed but remains quite long.
    file_ir = example_environment_f.target_ir

    fn_a_target = IrTarget(
        symbol=(fn_a := Func(name="fn_a", interface=CallInterface(args=("a",)))),
        ir=file_ir[fn_a],
    )
    fn_b_target = IrTarget(
        symbol=(fn_b := Func(name="fn_b", interface=CallInterface(args=("b",)))),
        ir=file_ir[fn_b],
    )
    fn_c_target = IrTarget(
        symbol=(fn_c := Func(name="fn_c", interface=CallInterface(args=("c",)))),
        ir=file_ir[fn_c],
    )

    fn_a_actual = make_target_ir_call_tree(
        fn_a_target,
        environment=example_environment_f,
    )
    fn_a_expected = IrCallTreeNode(
        target=fn_a_target,
        edge_in=None,
        edges_out=[
            fn_a_to_fn_a_call := IrCall(
                caller=fn_a,
                symbol=Call(name="fn_a", args=CallArguments(args=("a",)), target=fn_a),
            ),
            fn_a_to_fn_b_call := IrCall(
                caller=fn_a,
                symbol=Call(name="fn_b", args=CallArguments(args=("a",)), target=fn_b),
            ),
        ],
        children=[
            IrCallTreeNode(
                target=fn_a_target,
                edge_in=fn_a_to_fn_a_call,
                edges_out=[
                    fn_a_to_fn_a_call,  # direct recursion
                    fn_a_to_fn_b_call,
                ],
                children=[],
            ),
            IrCallTreeNode(
                target=fn_b_target,
                edge_in=fn_a_to_fn_b_call,
                edges_out=[
                    # indirect recursion: a -> b -> a
                    fn_b_to_a_call := IrCall(
                        caller=fn_b,
                        symbol=Call(
                            name="fn_a",
                            args=CallArguments(args=("b",)),
                            target=fn_a,
                        ),
                    ),
                    fn_b_to_c_call := IrCall(
                        caller=fn_b,
                        symbol=Call(
                            name="fn_c",
                            args=CallArguments(args=("b",)),
                            target=fn_c,
                        ),
                    ),
                ],
                children=[
                    # from above indirect recursion
                    # thus this is a repeat of root with a different edge_in
                    # but without children (cycle elimination)
                    IrCallTreeNode(
                        target=fn_a_target,
                        edge_in=fn_b_to_a_call,
                        edges_out=[
                            fn_a_to_fn_a_call,
                            fn_a_to_fn_b_call,
                        ],
                        children=[],
                    ),
                    IrCallTreeNode(
                        target=fn_c_target,
                        edge_in=fn_b_to_c_call,
                        edges_out=[
                            fn_c_to_fn_b_call := IrCall(
                                caller=fn_c,
                                symbol=Call(
                                    name="fn_b",
                                    args=CallArguments(args=("c",)),
                                    target=fn_b,
                                ),
                            ),
                        ],
                        children=[
                            IrCallTreeNode(
                                target=fn_b_target,
                                edge_in=fn_c_to_fn_b_call,
                                edges_out=[fn_b_to_a_call, fn_b_to_c_call],
                                children=[],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    assert fn_a_actual == fn_a_expected

    fn_b_actual = make_target_ir_call_tree(
        fn_b_target,
        environment=example_environment_f,
    )
    fn_b_expected = IrCallTreeNode(
        target=fn_b_target,
        edge_in=None,
        edges_out=[
            fn_b_to_a_call,
            fn_b_to_c_call,
        ],
        children=[
            IrCallTreeNode(
                target=fn_a_target,
                edge_in=fn_b_to_a_call,
                edges_out=[
                    fn_a_to_fn_a_call,
                    fn_a_to_fn_b_call,
                ],
                children=[
                    IrCallTreeNode(
                        target=fn_a_target,
                        edge_in=fn_a_to_fn_a_call,
                        edges_out=[
                            fn_a_to_fn_a_call,
                            fn_a_to_fn_b_call,
                        ],
                        children=[],
                    ),
                    IrCallTreeNode(
                        target=fn_b_target,
                        edge_in=fn_a_to_fn_b_call,
                        edges_out=[
                            fn_b_to_a_call,
                            fn_b_to_c_call,
                        ],
                        children=[],
                    ),
                ],
            ),
            IrCallTreeNode(
                target=fn_c_target,
                edge_in=fn_b_to_c_call,
                edges_out=[fn_c_to_fn_b_call],
                children=[
                    IrCallTreeNode(
                        target=fn_b_target,
                        edge_in=fn_c_to_fn_b_call,
                        edges_out=[
                            fn_b_to_a_call,
                            fn_b_to_c_call,
                        ],
                        children=[],
                    ),
                ],
            ),
        ],
    )
    assert fn_b_actual == fn_b_expected

    fn_c_actual = make_target_ir_call_tree(
        fn_c_target,
        environment=example_environment_f,
    )
    fn_c_expected = IrCallTreeNode(
        target=fn_c_target,
        edge_in=None,
        edges_out=[fn_c_to_fn_b_call],
        children=[
            IrCallTreeNode(
                target=fn_b_target,
                edge_in=fn_c_to_fn_b_call,
                edges_out=[
                    fn_b_to_a_call,
                    fn_b_to_c_call,
                ],
                children=[
                    IrCallTreeNode(
                        target=fn_a_target,
                        edge_in=fn_b_to_a_call,
                        edges_out=[
                            fn_a_to_fn_a_call,
                            fn_a_to_fn_b_call,
                        ],
                        children=[
                            IrCallTreeNode(
                                target=fn_a_target,
                                edge_in=fn_a_to_fn_a_call,
                                edges_out=[
                                    fn_a_to_fn_a_call,
                                    fn_a_to_fn_b_call,
                                ],
                                children=[],
                            ),
                            IrCallTreeNode(
                                target=fn_b_target,
                                edge_in=fn_a_to_fn_b_call,
                                edges_out=[
                                    fn_b_to_a_call,
                                    fn_b_to_c_call,
                                ],
                                children=[],
                            ),
                        ],
                    ),
                    IrCallTreeNode(
                        target=fn_c_target,
                        edge_in=fn_b_to_c_call,
                        edges_out=[fn_c_to_fn_b_call],
                        children=[],
                    ),
                ],
            ),
        ],
    )
    assert fn_c_actual == fn_c_expected

    _, stderr = capfd.readouterr()
    assert match_output(stderr, [])
