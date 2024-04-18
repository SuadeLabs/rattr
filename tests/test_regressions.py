from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

import pytest

import tests.helpers as helpers
from rattr.analyser.file import FileAnalyser
from rattr.models.context import compile_root_context
from rattr.models.ir import FileIr
from rattr.models.results import FileResults
from rattr.models.symbol import (
    Builtin,
    Call,
    CallArguments,
    CallInterface,
    Class,
    Func,
    Import,
    Name,
)
from rattr.results import generate_results_from_ir
from tests.shared import match_output

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from tests.shared import ArgumentsFn, MakeRootContextFn, ParseFn, StateFn


@pytest.fixture(autouse=True)
def __set_current_file(state: StateFn) -> Iterator[None]:
    with state(current_file=Path("target.py")):
        yield


class TestRegression:
    def test_highly_nested(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        _ast = parse(
            """
            def getter(a):
                *a.b[0]().c

            def setter(a):
                *a.b[0]().c = "a value"
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        getter_symbol = Func(name="getter", interface=CallInterface(args=("a",)))
        setter_symbol = Func(name="setter", interface=CallInterface(args=("a",)))

        expected = FileIr(
            context=make_root_context(
                [
                    getter_symbol,
                    setter_symbol,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                getter_symbol: {
                    "gets": {Name("*a.b[]().c", "a")},
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
                setter_symbol: {
                    "gets": set(),
                    "sets": {Name("*a.b[]().c", "a")},
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_tuple_assignment(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        _ast = parse(
            """
            def getter(a):
                x, y = a.attr_a, a.attr_b

            def setter(a):
                a.attr_a, a.attr_b = x, y
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        getter_symbol = Func(name="getter", interface=CallInterface(args=("a",)))
        setter_symbol = Func(name="setter", interface=CallInterface(args=("a",)))

        expected = FileIr(
            context=make_root_context(
                [
                    getter_symbol,
                    setter_symbol,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                getter_symbol: {
                    "gets": {
                        Name("a.attr_a", "a"),
                        Name("a.attr_b", "a"),
                    },
                    "sets": {
                        Name("x"),
                        Name("y"),
                    },
                    "dels": set(),
                    "calls": set(),
                },
                setter_symbol: {
                    "gets": {
                        Name("x"),
                        Name("y"),
                    },
                    "sets": {
                        Name("a.attr_a", "a"),
                        Name("a.attr_b", "a"),
                    },
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_operation_on_anonymous_return_value(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        constant: str,
    ):
        _ast = parse(
            """
            def test_1(a):
                # i.e. b.c and b.d are of a type that implements __add__
                a = max((b.c + b.d).method(), 0)

            def test_2(a):
                return (-b).c
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        max_symbol = Builtin(name="max")
        getter_symbol = Func(name="test_1", interface=CallInterface(args=("a",)))
        setter_symbol = Func(name="test_2", interface=CallInterface(args=("a",)))

        expected = FileIr(
            context=make_root_context(
                [
                    getter_symbol,
                    setter_symbol,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                getter_symbol: {
                    "gets": set(),
                    "sets": {Name("a")},
                    "dels": set(),
                    "calls": {
                        Call(
                            name="@BinOp.method()",
                            args=CallArguments(args=(), kwargs={}),
                            target=None,
                        ),
                        Call(
                            name="max()",
                            args=CallArguments(
                                args=("@BinOp.method()", constant),
                                kwargs={},
                            ),
                            target=max_symbol,
                        ),
                    },
                },
                setter_symbol: {
                    "gets": {
                        Name("b"),
                        Name("@UnaryOp.c", "@UnaryOp"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_resolve_getattr_name(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        _ast = parse(
            """
            def act(on):
                return on.attr

            def a_func(arg):
                return act(getattr(arg, "attr"))
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        fn_act = Func(name="act", interface=CallInterface(args=("on",)))
        fn_a = Func(name="a_func", interface=CallInterface(args=("arg",)))

        expected = FileIr(
            context=make_root_context(
                [
                    fn_act,
                    fn_a,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                fn_act: {
                    "gets": {Name("on.attr", "on")},
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
                fn_a: {
                    "gets": {
                        Name("arg"),
                        Name("arg.attr", "arg"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": {
                        Call(
                            name="act()",
                            args=CallArguments(args=("arg.attr",), kwargs={}),
                            target=fn_act,
                        ),
                    },
                },
            },
        )

        assert results == expected

    def test_procedural_parameter(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        capfd: pytest.CaptureFixture[str],
    ):
        # NOTE
        # Higher-order functions will not give the "correct" results as they can't
        # realistically be resolved, however, they should not cause a crash or a fatal
        # error.

        # Procedural parameter
        _ast = parse(
            """
            def bad_map(f, target):
                # like map but... bad
                return f(target)
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        bad_map = Func(name="bad_map", interface=CallInterface(args=("f", "target")))
        expected = FileIr(
            context=make_root_context(
                [
                    bad_map,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                bad_map: {
                    "gets": {Name("target")},
                    "sets": set(),
                    "dels": set(),
                    "calls": {
                        Call(
                            name="f()",
                            args=CallArguments(args=("target",), kwargs={}),
                            target=Name("f"),
                        ),
                    },
                }
            },
        )

        assert results._file_ir[bad_map]["calls"] == expected._file_ir[bad_map]["calls"]
        assert results == expected

        _, stderr = capfd.readouterr()
        assert match_output(
            stderr,
            [
                "unable to resolve call to 'f()', target is likely a procedural "
                "parameter",
            ],
        )

    def test_local_function_as_return_value(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        capfd: pytest.CaptureFixture[str],
    ):
        # Procedural return value
        _ast = parse(
            """
            def wrapper():
                def inner():
                    return "some value"
                return inner

            def actor():
                return wrapper()()
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        wrapper = Func(name="wrapper", interface=CallInterface(args=()))
        actor = Func(name="actor", interface=CallInterface(args=()))

        expected = FileIr(
            context=make_root_context(
                [
                    wrapper,
                    actor,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                wrapper: {
                    "gets": {Name("inner")},
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
                actor: {
                    "gets": set(),
                    "sets": set(),
                    "dels": set(),
                    "calls": {
                        Call(
                            name="wrapper",
                            args=CallArguments(args=(), kwargs={}),
                            target=wrapper,
                        ),
                    },
                },
            },
        )

        assert results._file_ir[actor]["calls"] == expected._file_ir[actor]["calls"]
        assert results == expected

        _, stderr = capfd.readouterr()
        assert match_output(
            stderr,
            [
                "unable to unbind nested functions",
                "unable to resolve call to 'wrapper()()', target is a call on a call",
            ],
        )

    def test_iterate_over_list_of_functions(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        capfd: pytest.CaptureFixture[str],
    ):
        # Local function
        # Technically not higher-order, but w/e
        _ast = parse(
            """
            def fn_a(arg):
                return arg.a

            def fn_b(arg):
                return arg.b

            def bad(argument) -> int:
                accumulator = 0

                for f in [fn_a, fn_b]:
                    accumulator += f(argument)

                return accumulator
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        fn_a = Func(name="fn_a", interface=CallInterface(args=("arg",)))
        fn_b = Func(name="fn_b", interface=CallInterface(args=("arg",)))
        bad = Func(name="bad", interface=CallInterface(args=("argument",)))

        expected = FileIr(
            context=make_root_context(
                [
                    fn_a,
                    fn_b,
                    bad,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                fn_a: {
                    "gets": {Name("arg.a", "arg")},
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
                fn_b: {
                    "gets": {Name("arg.b", "arg")},
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
                bad: {
                    "gets": {
                        Name("accumulator"),
                        Name("fn_a"),
                        Name("fn_b"),
                        Name("argument"),
                    },
                    "sets": {
                        Name("accumulator"),
                        Name("f"),
                    },
                    "dels": set(),
                    "calls": {
                        Call(
                            name="f()",
                            args=CallArguments(args=("argument",), kwargs={}),
                            target=Name("f"),
                        ),
                    },
                },
            },
        )

        assert results == expected

        _, stderr = capfd.readouterr()
        assert "likely a procedural parameter" in stderr

    def test_regression_generator_iterable_is_literal(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        _ast = parse(
            """
            def fn():
                list_of_tuples = [
                    ("first", [
                        e.whatever for e in [thing_one, thing_two]
                    ])
                ]
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        fn_symbol = Func(name="fn", interface=CallInterface(args=()))
        expected = FileIr(
            context=make_root_context(
                [
                    fn_symbol,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                fn_symbol: {
                    "gets": {
                        Name("thing_one"),
                        Name("thing_two"),
                        Name("e.whatever", "e"),
                    },
                    "sets": {
                        Name("e"),
                        Name("list_of_tuples"),
                    },
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

    def test_regression_generator_iterable_is_literal_rhs_is_singlet(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        _ast = parse(
            """
            def fn():
                list_of_tuples = [
                    ("first", [
                        e.whatever for e in [thing]
                    ])
                ]
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        fn_symbol = Func(name="fn", interface=CallInterface(args=()))
        expected = FileIr(
            context=make_root_context(
                [
                    fn_symbol,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                fn_symbol: {
                    "gets": {
                        Name("thing"),
                        Name("e.whatever", "e"),
                    },
                    "sets": {
                        Name("e"),
                        Name("list_of_tuples"),
                    },
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

    def test_regression_gets_in_bin_op(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        # ALWAYS WORKED
        # Test if "arg.first" and "arg.second" are in "gets"
        _ast = parse(
            """
            def fn(arg):
                return (arg.first + arg.second)
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        fn_symbol = Func(name="fn", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [
                    fn_symbol,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                fn_symbol: {
                    "gets": {
                        Name("arg.first", "arg"),
                        Name("arg.second", "arg"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

    def test_regression_attr_access_on_bin_op_result(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        # REGRESSION
        # Test if "arg.first" and "arg.second" are in "gets"
        _ast = parse(
            """
            def fn(arg):
                return (arg.first + arg.second).some_property
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        fn_symbol = Func(name="fn", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [
                    fn_symbol,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                fn_symbol: {
                    "gets": {
                        Name("arg.first", "arg"),
                        Name("arg.second", "arg"),
                        Name("@BinOp.some_property", "@BinOp"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

    def test_regression_bin_op_result_in_starred_expression(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        # REGRESSION
        _ast = parse(
            """
            def fn(arg):
                return call(*[arg.first + arg.second])
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        fn_symbol = Func(name="fn", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [
                    fn_symbol,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                fn_symbol: {
                    "gets": {
                        Name("arg.first", "arg"),
                        Name("arg.second", "arg"),
                        Name("*@List", "@List"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": {
                        Call(
                            name="call()",
                            args=CallArguments(args=("*@List",), kwargs={}),
                            target=None,
                        ),
                    },
                }
            },
        )

        assert results == expected

    def test_regression_subscript_on_bin_op_result(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        _ast = parse(
            """
            def fn(arg):
                return (arg.first + arg.second)["index"]
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        fn_symbol = Func(name="fn", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [
                    fn_symbol,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                fn_symbol: {
                    "gets": {
                        Name("arg.first", "arg"),
                        Name("arg.second", "arg"),
                        Name("@BinOp[]", "@BinOp"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

    def test_regression_gets_attr(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        # ALWAYS WORKED
        _ast = parse(
            """
            def fn(arg):
                return arg.attr
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        fn_symbol = Func(name="fn", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [
                    fn_symbol,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                fn_symbol: {
                    "gets": {Name("arg.attr", "arg")},
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

    def test_regression_gets_attr_of_method_call(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        arguments: ArgumentsFn,
        capfd: pytest.CaptureFixture[str],
    ):
        # ALWAYS WORKED
        _ast = parse(
            """
            def fn(arg):
                return arg.method()
            """
        )

        with arguments(_warning_level="all"):
            results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        fn_symbol = Func(name="fn", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [
                    fn_symbol,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                fn_symbol: {
                    "gets": set(),
                    "sets": set(),
                    "dels": set(),
                    "calls": {
                        Call(
                            name="arg.method()",
                            args=CallArguments(args=(), kwargs=[]),
                            target=None,
                        ),
                    },
                }
            },
        )

        assert results == expected

        _, stderr = capfd.readouterr()
        assert match_output(
            stderr,
            [
                "unable to resolve call to 'arg.method()', target is a method",
            ],
        )

    def test_regression_gets_attr_of_method_parent_on_call(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        # REGRESSION 1
        _ast = parse(
            """
            def fn(arg):
                return arg.attr.method()
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        fn_symbol = Func(name="fn", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [
                    fn_symbol,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                fn_symbol: {
                    "gets": {Name("arg.attr", "arg")},
                    "sets": set(),
                    "dels": set(),
                    "calls": {
                        Call(
                            name="arg.attr.method()",
                            args=CallArguments(args=(), kwargs={}),
                            target=None,
                        ),
                    },
                }
            },
        )

        assert results == expected

    def test_regression_gets_attrs_of_deep_method_parents_on_call(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        # REGRESSION 2
        _ast = parse(
            """
            def fn(arg):
                return arg.a.b.c.d.method()
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        fn_symbol = Func(name="fn", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [
                    fn_symbol,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                fn_symbol: {
                    "gets": {
                        Name("arg.a", "arg"),
                        Name("arg.a.b", "arg"),
                        Name("arg.a.b.c", "arg"),
                        Name("arg.a.b.c.d", "arg"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": {
                        Call(
                            name="arg.a.b.c.d.method()",
                            args=CallArguments(args=(), kwargs={}),
                            target=None,
                        ),
                    },
                }
            },
        )

        assert results == expected


class TestNamedTupleFromCall:
    # Test namedtuples constructed by calls to `collections.namedtuple`.
    # This failed at analyse, not simplification, but we should confirm that it passes
    # simplification nonetheless.

    @pytest.fixture(autouse=True)
    def __test_in_strict_mode(self, arguments) -> Iterator[None]:
        with arguments(is_strict=True):
            yield

    def test_call_with_positional_arguments(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        constant: str,
    ):
        _ast = parse(
            """
            from collections import namedtuple

            point = namedtuple("point", ["x", "y"])

            def by_pos():
                return point(1, 2)
            """
        )

        # This failed at analyse, but we should show that simplification also works
        with mock.patch("sys.exit") as _exit:
            file_ir = FileAnalyser(_ast, compile_root_context(_ast)).analyse()
            _ = generate_results_from_ir(target_ir=file_ir, import_irs={})

        namedtuple_import = Import(
            name="namedtuple",
            qualified_name="collections.namedtuple",
        )
        point = Class(
            name="point",
            interface=CallInterface(args=("self", "x", "y")),
        )
        point_call = Call(
            name="point()",
            args=CallArguments(
                args=("@ReturnValue", constant, constant),
                kwargs={},
            ),
            target=point,
        )
        by_pos = Func(name="by_pos", interface=CallInterface(args=()))

        expected = FileIr(
            context=make_root_context(
                [
                    namedtuple_import,
                    point,
                    by_pos,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                point: {
                    "gets": set(),
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
                by_pos: {
                    "gets": set(),
                    "sets": set(),
                    "dels": set(),
                    "calls": {point_call},
                },
            },
        )

        assert file_ir == expected
        assert _exit.call_count == 0

    def test_call_with_keyword_arguments(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        constant: str,
    ):
        _ast = parse(
            """
            from collections import namedtuple

            point = namedtuple("point", ["x", "y"])

            def by_keyword():
                return point(x=1, y=2)
            """
        )

        # This failed at analyse, but we should show that simplification also works
        with mock.patch("sys.exit") as _exit:
            file_ir = FileAnalyser(_ast, compile_root_context(_ast)).analyse()
            _ = generate_results_from_ir(target_ir=file_ir, import_irs={})

        namedtuple_import = Import(
            name="namedtuple",
            qualified_name="collections.namedtuple",
        )
        point = Class(
            name="point",
            interface=CallInterface(args=("self", "x", "y")),
        )
        point_call = Call(
            name="point()",
            args=CallArguments(
                args=("@ReturnValue",),
                kwargs={"x": constant, "y": constant},
            ),
            target=point,
        )
        by_keyword = Func(name="by_keyword", interface=CallInterface(args=()))

        expected = FileIr(
            context=make_root_context(
                [
                    namedtuple_import,
                    point,
                    by_keyword,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                point: {
                    "gets": set(),
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
                by_keyword: {
                    "gets": set(),
                    "sets": set(),
                    "dels": set(),
                    "calls": {point_call},
                },
            },
        )

        assert file_ir == expected
        assert _exit.call_count == 0

    def test_call_with_positional_and_keyword_arguments(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        constant: str,
    ):
        _ast = parse(
            """
            from collections import namedtuple

            point = namedtuple("point", ["x", "y"])

            def by_mixture():
                return point(1, y=2)
            """
        )

        # This failed at analyse, but we should show that simplification also works
        with mock.patch("sys.exit") as _exit:
            file_ir = FileAnalyser(_ast, compile_root_context(_ast)).analyse()
            _ = generate_results_from_ir(target_ir=file_ir, import_irs={})

        namedtuple_import = Import(
            name="namedtuple",
            qualified_name="collections.namedtuple",
        )
        point = Class(
            name="point",
            interface=CallInterface(args=("self", "x", "y")),
        )
        point_call = Call(
            name="point()",
            args=CallArguments(
                args=("@ReturnValue", constant),
                kwargs={"y": constant},
            ),
            target=point,
        )
        by_mixture = Func(name="by_mixture", interface=CallInterface(args=()))

        expected = FileIr(
            context=make_root_context(
                [
                    namedtuple_import,
                    point,
                    by_mixture,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                point: {
                    "gets": set(),
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
                by_mixture: {
                    "gets": set(),
                    "sets": set(),
                    "dels": set(),
                    "calls": {point_call},
                },
            },
        )

        assert file_ir == expected
        assert _exit.call_count == 0

    def test_locally_defined_named_tuple(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        constant: str,
        capfd: pytest.CaptureFixture[str],
    ):
        _ast = parse(
            """
            from collections import namedtuple

            def fn():
                point = namedtuple("point", ["x", "y"])
                return point(1, y=2)
            """
        )

        # This failed at analyse, but we should show that simplification also works
        with mock.patch("sys.exit") as _exit:
            file_ir = FileAnalyser(_ast, compile_root_context(_ast)).analyse()
            _ = generate_results_from_ir(target_ir=file_ir, import_irs={})

        namedtuple_import = Import(
            name="namedtuple",
            qualified_name="collections.namedtuple",
        )
        point = Class(
            name="point",
            interface=CallInterface(args=("self", "x", "y")),
        )
        point_call = Call(
            name="point()",
            args=CallArguments(
                args=("@ReturnValue", constant),
                kwargs={"y": constant},
            ),
            target=point,
        )
        fn = Func(name="fn", interface=CallInterface(args=()))

        expected = FileIr(
            context=make_root_context(
                [
                    namedtuple_import,
                    fn,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                fn: {
                    "gets": set(),
                    "sets": set(),
                    "dels": set(),
                    "calls": {point_call},
                },
            },
        )

        # `point` is defined as a local callable, which is no yet supported, thus this
        # should fail in strict mode.
        assert file_ir == expected
        assert _exit.call_count == 1

        # TODO Why is the output repeated here?
        _, stderr = capfd.readouterr()
        assert match_output(
            stderr,
            [
                "unable to resolve initialiser for 'point'",
                "unable to resolve initialiser for 'point'",
            ],
        )

    def test_call_with_space_delimited_string_argument(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        constant: str,
    ):
        _ast = parse(
            """
            from collections import namedtuple

            point = namedtuple("point", "x y")

            def my_function():
                return point(1, y=2)
            """
        )

        # This failed at analyse, but we should show that simplification also works
        with mock.patch("sys.exit") as _exit:
            file_ir = FileAnalyser(_ast, compile_root_context(_ast)).analyse()
            _ = generate_results_from_ir(target_ir=file_ir, import_irs={})

        namedtuple_import = Import(
            name="namedtuple",
            qualified_name="collections.namedtuple",
        )
        point = Class(
            name="point",
            interface=CallInterface(args=("self", "x", "y")),
        )
        point_call = Call(
            name="point()",
            args=CallArguments(
                args=("@ReturnValue", constant),
                kwargs={"y": constant},
            ),
            target=point,
        )
        my_function = Func(name="my_function", interface=CallInterface(args=()))

        expected = FileIr(
            context=make_root_context(
                [
                    namedtuple_import,
                    point,
                    my_function,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                point: {
                    "gets": set(),
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
                my_function: {
                    "gets": set(),
                    "sets": set(),
                    "dels": set(),
                    "calls": {point_call},
                },
            },
        )

        assert file_ir == expected
        assert _exit.call_count == 0


class TestNamedTupleFromInheritance:
    # Test namedtuples constructed by inheriting from `typing.NamedTuple`.
    # This previously had a fatal error at simplification.

    @pytest.fixture(autouse=True)
    def __test_in_strict_mode(self, arguments: ArgumentsFn) -> Iterator[None]:
        with arguments(is_strict=True):
            yield

    def test_call_with_positional_arguments(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        constant: str,
    ):
        _ast = parse(
            """
            from typing import NamedTuple

            class Point(NamedTuple):
                x: int
                y: int

            def by_pos():
                return Point(1, 2)
            """
        )

        with mock.patch("sys.exit") as _exit:
            file_ir = FileAnalyser(_ast, compile_root_context(_ast)).analyse()
            _ = generate_results_from_ir(target_ir=file_ir, import_irs={})

        namedtuple_import = Import(
            name="NamedTuple",
            qualified_name="typing.NamedTuple",
        )
        point = Class(
            name="Point",
            interface=CallInterface(args=("self", "x", "y")),
        )
        point_x = Name(name="Point.x", basename="Point")
        point_y = Name(name="Point.y", basename="Point")
        point_call = Call(
            "Point()",
            args=CallArguments(
                args=("@ReturnValue", constant, constant),
                kwargs={},
            ),
            target=point,
        )
        by_pos = Func(name="by_pos", interface=CallInterface(args=()))

        expected = FileIr(
            context=make_root_context(
                [
                    namedtuple_import,
                    point,
                    point_x,
                    point_y,
                    by_pos,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                point: {
                    "gets": set(),
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
                by_pos: {
                    "gets": set(),
                    "sets": set(),
                    "dels": set(),
                    "calls": {point_call},
                },
            },
        )

        assert file_ir == expected
        assert _exit.call_count == 0

    def test_call_with_keyword_arguments(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        constant: str,
    ):
        _ast = parse(
            """
            from typing import NamedTuple

            class Point(NamedTuple):
                x: int
                y: int

            def by_keyword():
                return Point(x=1, y=2)
            """
        )

        # Before the fix this failed at the simplification in "generate_results_from_ir"
        with mock.patch("sys.exit") as _exit:
            file_ir = FileAnalyser(_ast, compile_root_context(_ast)).analyse()
            _ = generate_results_from_ir(target_ir=file_ir, import_irs={})

        namedtuple_import = Import(
            name="NamedTuple",
            qualified_name="typing.NamedTuple",
        )
        point = Class(
            name="Point",
            interface=CallInterface(args=("self", "x", "y")),
        )
        point_x = Name(name="Point.x", basename="Point")
        point_y = Name(name="Point.y", basename="Point")
        point_call = Call(
            name="Point()",
            args=CallArguments(
                args=("@ReturnValue",),
                kwargs={"x": constant, "y": constant},
            ),
            target=point,
        )
        by_keyword = Func(name="by_keyword", interface=CallInterface(args=()))

        expected = FileIr(
            context=make_root_context(
                [
                    namedtuple_import,
                    point,
                    point_x,
                    point_y,
                    by_keyword,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                point: {
                    "gets": set(),
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
                by_keyword: {
                    "gets": set(),
                    "sets": set(),
                    "dels": set(),
                    "calls": {point_call},
                },
            },
        )

        assert file_ir == expected
        assert _exit.call_count == 0

    def test_call_with_positional_and_keyword_arguments(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        constant: str,
    ):
        _ast = parse(
            """
            from typing import NamedTuple

            class Point(NamedTuple):
                x: int
                y: int

            def by_mixture():
                return Point(1, y=2)
            """
        )

        # Before the fix this failed at the simplification in "generate_results_from_ir"
        with mock.patch("sys.exit") as _exit:
            file_ir = FileAnalyser(_ast, compile_root_context(_ast)).analyse()
            _ = generate_results_from_ir(target_ir=file_ir, import_irs={})

        namedtuple_import = Import(
            name="NamedTuple",
            qualified_name="typing.NamedTuple",
        )
        point = Class(
            name="Point",
            interface=CallInterface(args=("self", "x", "y")),
        )
        point_x = Name(name="Point.x", basename="Point")
        point_y = Name(name="Point.y", basename="Point")
        point_call = Call(
            name="Point()",
            args=CallArguments(
                args=("@ReturnValue", constant),
                kwargs={"y": constant},
            ),
            target=point,
        )
        by_mixture = Func(name="by_mixture", interface=CallInterface(args=()))

        expected = FileIr(
            context=make_root_context(
                [
                    namedtuple_import,
                    point,
                    point_x,
                    point_y,
                    by_mixture,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                point: {
                    "gets": set(),
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
                by_mixture: {
                    "gets": set(),
                    "sets": set(),
                    "dels": set(),
                    "calls": {point_call},
                },
            },
        )

        assert file_ir == expected
        assert _exit.call_count == 0


class TestRattrConstantInNameableOnCheckForNamedTuple:
    """
    Brief:
    On checking if there is a named-tuple in the right-hand side of an expression,
    when the right hand side is a non-safely nameable expression an error is given.

    Introduced: 0.1.7
    Fixed: 0.1.8
    """

    def test_safely_determine_rhs_name_on_namedtuple_check(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        constant: str,
        arguments: ArgumentsFn,
        capfd: pytest.CaptureFixture[str],
    ):
        _ast = parse(
            """
            def my_function(foobar, info=None):
                i_cause_the_error = "_".join(info.parts)
            """
        )

        with mock.patch("sys.exit") as _exit, arguments(_warning_level="all"):
            file_ir = FileAnalyser(_ast, compile_root_context(_ast)).analyse()
            _ = generate_results_from_ir(target_ir=file_ir, import_irs={})

        my_function = Func(
            name="my_function",
            interface=CallInterface(args=("foobar", "info")),
        )
        string_join = f"{constant}.join()"
        string_join_call = Call(
            string_join,
            args=CallArguments(args=("info.parts",), kwargs={}),
        )

        expected = FileIr(
            context=make_root_context(
                [
                    my_function,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                my_function: {
                    "gets": {Name("info.parts", basename="info")},
                    "sets": {Name("i_cause_the_error")},
                    "dels": set(),
                    "calls": {string_join_call},
                }
            },
        )

        assert file_ir == expected
        assert not _exit.called

        _, stderr = capfd.readouterr()
        assert match_output(
            stderr,
            [
                "unable to resolve call to '@Constant.join()', target lhs is a literal",
            ],
        )


@pytest.mark.usefixtures("run_in_strict_mode")
class TestGeneratorAndComprehensionsAreDeeplyVisited:
    def test_generator_expression(
        self,
        analyse_single_file: Callable[[str], tuple[FileIr, FileResults]],
        make_root_context: MakeRootContextFn,
        capfd: pytest.CaptureFixture[str],
    ):
        file_ir, file_results = analyse_single_file(
            """
            def fn(xss):
                return (
                    x.attr
                    for xs in xss
                    for x in (
                        _x
                        for _x in xs
                        if _x.is_usable
                    )
                    if x.other_attr > 10
                )
            """
        )

        _, stderr = capfd.readouterr()
        assert helpers.stderr_matches(stderr, [])

        symbols = {
            "fn": Func("fn", interface=CallInterface(args=("xss",))),
        }
        expected_file_ir = FileIr(
            context=make_root_context(symbols.values(), include_root_symbols=True),
            file_ir={
                symbols["fn"]: {
                    "gets": {
                        Name("x.attr", "x"),
                        Name("xss"),
                        Name("_x"),
                        Name("xs"),
                        Name("_x.is_usable", "_x"),
                        Name("x.other_attr", "x"),
                    },
                    "sets": {
                        Name("xs"),
                        Name("x"),
                        Name("_x"),
                    },
                    "dels": set(),
                    "calls": set(),
                }
            },
        )
        expected_file_results = FileResults(
            {
                "fn": {
                    "gets": {
                        "_x",
                        "_x.is_usable",
                        "xs",
                        "xss",
                        "x.other_attr",
                        "x.attr",
                    },
                    "sets": {"_x", "xs", "x"},
                    "dels": set(),
                    "calls": set(),
                }
            }
        )

        assert file_ir == expected_file_ir
        assert file_results == expected_file_results

    def test_simple_ternary_in_generator_expression(
        self,
        analyse_single_file: Callable[[str], tuple[FileIr, FileResults]],
        make_root_context: MakeRootContextFn,
        capfd: pytest.CaptureFixture[str],
        builtin: Callable[[str], Builtin],
    ):
        file_ir, file_results = analyse_single_file(
            """
            def fn(foos):
                return any(foo.bar if foo.bar else foo.baz for foo in foos)
            """
        )

        _, stderr = capfd.readouterr()
        assert helpers.stderr_matches(stderr, [])

        symbols = {
            "fn": Func("fn", interface=CallInterface(args=("foos",))),
        }
        expected_file_ir = FileIr(
            context=make_root_context(symbols.values(), include_root_symbols=True),
            file_ir={
                symbols["fn"]: {
                    "gets": {
                        Name("foo.bar", "foo"),
                        Name("foo.baz", "foo"),
                        Name("foos"),
                    },
                    "sets": {
                        Name("foo"),
                    },
                    "dels": set(),
                    "calls": {
                        Call(
                            "any()",
                            args=CallArguments(args=("@GeneratorExp",)),
                            target=builtin("any"),
                        ),
                    },
                }
            },
        )
        expected_file_results = FileResults(
            {
                "fn": {
                    "gets": {"foo.bar", "foo.baz", "foos"},
                    "sets": {"foo"},
                    "dels": set(),
                    "calls": {"any()"},
                }
            }
        )

        assert file_ir == expected_file_ir
        assert file_results == expected_file_results

    def test_simple_walrus_in_generator_expression(
        self,
        analyse_single_file: Callable[[str], tuple[FileIr, FileResults]],
        make_root_context: MakeRootContextFn,
        capfd: pytest.CaptureFixture[str],
        builtin: Callable[[str], Builtin],
    ):
        file_ir, file_results = analyse_single_file(
            """
            def fn(foos):
                return any(sum(baz) for foo in foos if (baz := foo.bars))
            """
        )

        _, stderr = capfd.readouterr()
        assert helpers.stderr_matches(stderr, [])

        symbols = {
            "fn": Func("fn", interface=CallInterface(args=("foos",))),
        }
        expected_file_ir = FileIr(
            context=make_root_context(symbols.values(), include_root_symbols=True),
            file_ir={
                symbols["fn"]: {
                    "gets": {
                        Name("foo.bars", "foo"),
                        Name("foos"),
                        Name("baz"),
                    },
                    "sets": {
                        Name("foo"),
                        Name("baz"),
                    },
                    "dels": set(),
                    "calls": {
                        Call(
                            "any",
                            args=CallArguments(args=("@GeneratorExp",)),
                            target=builtin("any"),
                        ),
                        Call(
                            "sum",
                            args=CallArguments(args=("baz",)),
                            target=builtin("sum"),
                        ),
                    },
                }
            },
        )
        expected_file_results = FileResults(
            {
                "fn": {
                    "gets": {"foo.bars", "foos", "baz"},
                    "sets": {"foo", "baz"},
                    "dels": set(),
                    "calls": {"any()", "sum()"},
                }
            }
        )

        assert file_ir == expected_file_ir
        assert file_results == expected_file_results

    def test_nested_ternary_in_generator_expression(
        self,
        analyse_single_file: Callable[[str], tuple[FileIr, FileResults]],
        make_root_context: MakeRootContextFn,
        capfd: pytest.CaptureFixture[str],
        builtin: Callable[[str], Builtin],
    ):
        file_ir, file_results = analyse_single_file(
            """
            def fn(foos):
                return any(f for f in [foo.bar if foo.bar else foo.baz for foo in foos])
            """
        )

        _, stderr = capfd.readouterr()
        assert helpers.stderr_matches(stderr, [])

        symbols = {
            "fn": Func("fn", interface=CallInterface(args=("foos",))),
        }
        expected_file_ir = FileIr(
            context=make_root_context(symbols.values(), include_root_symbols=True),
            file_ir={
                symbols["fn"]: {
                    "gets": {
                        Name("foo.bar", "foo"),
                        Name("foo.baz", "foo"),
                        Name("foos"),
                        Name("f"),
                    },
                    "sets": {
                        Name("foo"),
                        Name("f"),
                    },
                    "dels": set(),
                    "calls": {
                        Call(
                            "any()",
                            args=CallArguments(args=("@GeneratorExp",)),
                            target=builtin("any"),
                        ),
                    },
                }
            },
        )
        expected_file_results = FileResults(
            {
                "fn": {
                    "gets": {"foo.bar", "foo.baz", "foos", "f"},
                    "sets": {"foo", "f"},
                    "dels": set(),
                    "calls": {"any()"},
                }
            }
        )

        assert file_ir == expected_file_ir
        assert file_results == expected_file_results

    def test_nested_walrus_in_generator_expression(
        self,
        analyse_single_file: Callable[[str], tuple[FileIr, FileResults]],
        make_root_context: MakeRootContextFn,
        capfd: pytest.CaptureFixture[str],
        builtin: Callable[[str], Builtin],
    ):
        file_ir, file_results = analyse_single_file(
            """
            def fn(foos):
                return any(sum(b) for b in [baz for foo in foos if (baz := foo.bars)])
            """
        )

        _, stderr = capfd.readouterr()
        assert helpers.stderr_matches(stderr, [])

        symbols = {
            "fn": Func("fn", interface=CallInterface(args=("foos",))),
        }
        expected_file_ir = FileIr(
            context=make_root_context(symbols.values(), include_root_symbols=True),
            file_ir={
                symbols["fn"]: {
                    "gets": {
                        Name("foo.bars", "foo"),
                        Name("foos"),
                        Name("baz"),
                        Name("b"),
                    },
                    "sets": {
                        Name("foo"),
                        Name("baz"),
                        Name("b"),
                    },
                    "dels": set(),
                    "calls": {
                        Call(
                            "any()",
                            args=CallArguments(args=("@GeneratorExp",)),
                            target=builtin("any"),
                        ),
                        Call(
                            "sum()",
                            args=CallArguments(args=("b",)),
                            target=builtin("sum"),
                        ),
                    },
                }
            },
        )
        expected_file_results = FileResults(
            {
                "fn": {
                    "gets": {"foo.bars", "foos", "baz", "b"},
                    "sets": {"foo", "baz", "b"},
                    "dels": set(),
                    "calls": {"any()", "sum()"},
                }
            }
        )

        assert file_ir == expected_file_ir
        assert file_results == expected_file_results


@pytest.mark.usefixtures("run_in_permissive_mode")
class TestGeneratorAndComprehensionsAreDeeplyVisitedPermissive:
    def test_deeply_nested_comprehensions(
        self,
        analyse_single_file: Callable[[str], tuple[FileIr, FileResults]],
        make_root_context: MakeRootContextFn,
        capfd: pytest.CaptureFixture[str],
    ):
        file_ir, file_results = analyse_single_file(
            r"""
            from typing import Callable

            def fn(data):
                return {
                    datum.id: {
                        "foos": [foo.as_dict() for foo in datum.foos if foo.is_usable],
                        "unique_foo_ids": {foo.id for foo in datum.foos},
                        "flattened_positive_bars": [
                            row.bar
                            for col in datum.grid
                            for row in col
                            if row.bar.attr > 0
                        ],
                        "stuff": [
                            nested_s
                            for s in (
                                ss
                                for ss in datum.ss
                                if any(
                                    p()
                                    for p in ss.predicates
                                    if isinstance(p, Callable)
                                )
                            )
                            for nested_s in s
                        ]
                    }
                    for datum in data
                    if datum.id is not None
                }
            """
        )

        _, stderr = capfd.readouterr()
        assert (
            "unable to resolve call to 'p()', target is likely a procedural parameter"
            in stderr
        )

        symbols = {
            "callable": Import(name="Callable", qualified_name="typing.Callable"),
            "fn": Func("fn", interface=CallInterface(args=("data",))),
        }
        expected_file_ir = FileIr(
            context=make_root_context(symbols.values(), include_root_symbols=True),
            file_ir={
                symbols["fn"]: {
                    "gets": {
                        Name("datum.id", "datum"),
                        Name("datum.foos", "datum"),
                        Name("foo.is_usable", "foo"),
                        Name("foo.id", "foo"),
                        Name("row.bar", "row"),
                        Name("datum.grid", "datum"),
                        Name("col"),
                        Name("row.bar.attr", "row"),
                        Name("nested_s"),
                        Name("ss"),
                        Name("datum.ss", "datum"),
                        Name("p"),
                        Name("ss.predicates", "ss"),
                        Name("Callable"),
                        Name("s"),
                        Name("data"),
                    },
                    "sets": {
                        Name("foo"),
                        Name("col"),
                        Name("row"),
                        Name("s"),
                        Name("ss"),
                        Name("p"),
                        Name("nested_s"),
                        Name("datum"),
                    },
                    "dels": set(),
                    "calls": {
                        Call(
                            "any",
                            args=CallArguments(args=("@GeneratorExp",)),
                            target=Builtin("any"),
                        ),
                        Call("foo.as_dict", args=CallArguments(), target=None),
                        Call(
                            "isinstance",
                            args=CallArguments(args=("p", "Callable")),
                            target=Builtin("isinstance"),
                        ),
                        Call("p", args=CallArguments(), target=Name("p")),
                    },
                }
            },
        )
        expected_file_results = FileResults(
            {
                "fn": {
                    "gets": {
                        "data",
                        "s",
                        "nested_s",
                        "row.bar.attr",
                        "foo.id",
                        "Callable",
                        "datum.ss",
                        "datum.grid",
                        "p",
                        "foo.is_usable",
                        "ss",
                        "ss.predicates",
                        "row.bar",
                        "datum.id",
                        "datum.foos",
                        "col",
                    },
                    "sets": {"foo", "s", "nested_s", "datum", "row", "p", "ss", "col"},
                    "dels": set(),
                    "calls": {"p()", "isinstance()", "foo.as_dict()", "any()"},
                }
            }
        )

        assert file_ir == expected_file_ir
        assert file_results == expected_file_results
