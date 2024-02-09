from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

import tests.helpers as helpers
from rattr.analyser.file import FileAnalyser
from rattr.analyser.results import generate_results_from_ir
from rattr.models.context import compile_root_context
from rattr.models.symbol import (
    Builtin,
    Call,
    CallArguments,
    CallInterface,
    Class,
    Func,
    Name,
)

if TYPE_CHECKING:
    from typing import Callable, Iterator

    from rattr.analyser.types import FileIR, FileResults
    from rattr.models.context import Context
    from rattr.models.symbol import Symbol


class TestRegression:
    def test_highly_nested(self, parse):
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

        expected = {
            getter_symbol: {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("*a.b[]().c", "a"),
                },
                "sets": set(),
            },
            setter_symbol: {
                "calls": set(),
                "dels": set(),
                "gets": set(),
                "sets": {
                    Name("*a.b[]().c", "a"),
                },
            },
        }

        assert results == expected

    def test_tuple_assignment(self, parse):
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

        expected = {
            getter_symbol: {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("a.attr_a", "a"),
                    Name("a.attr_b", "a"),
                },
                "sets": {
                    Name("x"),
                    Name("y"),
                },
            },
            setter_symbol: {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("x"),
                    Name("y"),
                },
                "sets": {
                    Name("a.attr_a", "a"),
                    Name("a.attr_b", "a"),
                },
            },
        }

        assert results == expected

    def test_operation_on_anonymous_return_value(self, parse, constant):
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

        expected = {
            getter_symbol: {
                "calls": {
                    Call(
                        name="@BinOp.method()",
                        args=CallArguments(args=(), kwargs={}),
                        target=None,
                    ),
                    Call(
                        name="max()",
                        args=CallArguments(
                            args=("@BinOp.method()", constant("Num")),
                            kwargs={},
                        ),
                        target=max_symbol,
                    ),
                },
                "dels": set(),
                "gets": set(),
                "sets": {
                    Name("a"),
                },
            },
            setter_symbol: {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("b"),
                    Name("@UnaryOp.c", "@UnaryOp"),
                },
                "sets": set(),
            },
        }

        assert results == expected

    def test_resolve_getattr_name(self, parse):
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

        expected = {
            fn_act: {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("on.attr", "on"),
                },
                "sets": set(),
            },
            fn_a: {
                "calls": {
                    Call(
                        name="act()",
                        args=CallArguments(args=("arg.attr",), kwargs={}),
                        target=fn_act,
                    ),
                },
                "dels": set(),
                "gets": {
                    Name("arg.attr", "arg"),
                },
                "sets": set(),
            },
        }

        assert results == expected

    def test_higher_order_functions(self, parse, capfd):
        # NOTE
        #   Higher-order functions will not give the "correct" results as they
        #   can't realistically be statically resolved, however, they should
        #   not cause a crash or a fatal error.

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

        expected = {
            bad_map: {
                "sets": set(),
                "gets": {
                    Name("target"),
                },
                "dels": set(),
                "calls": {
                    Call(
                        name="f()",
                        args=CallArguments(args=("target",), kwargs={}),
                        target=Name("f"),
                    ),
                },
            }
        }

        assert results == expected

        _, stderr = capfd.readouterr()
        assert "likely a procedural parameter" in stderr

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

        expected = {
            wrapper: {
                "sets": set(),
                "gets": {
                    Name("inner"),
                },
                "dels": set(),
                "calls": set(),
            },
            actor: {
                "sets": set(),
                "gets": set(),
                "dels": set(),
                "calls": {
                    Call(
                        name="wrapper()()",
                        args=CallArguments(args=(), kwargs={}),
                        target=wrapper,
                    ),
                },
            },
        }

        assert results == expected

        _, stderr = capfd.readouterr()
        assert "unable to resolve call result of call" in stderr

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

        expected = {
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
        }

        assert results == expected

        _, stderr = capfd.readouterr()
        assert "likely a procedural parameter" in stderr

    def test_regression_generator_iterable_is_literal(self, parse):
        # List of many
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

        expected = {
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
        }

        assert results == expected

        # List of one
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

        expected = {
            fn_symbol: {
                "gets": {
                    Name("thing"),
                    Name("e.whatever", "e"),
                },
                "sets": {
                    Name("list_of_tuples"),
                    Name("e"),
                },
                "dels": set(),
                "calls": set(),
            }
        }

        assert results == expected

    def test_regression_gets_in_bin_op(self, parse):
        # NOTE in Python 3.8 support / tests for "sets" in BinOp will be needed

        #
        # In Attribute
        #

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

        expected = {
            fn_symbol: {
                "sets": set(),
                "gets": {
                    Name("arg.first", "arg"),
                    Name("arg.second", "arg"),
                },
                "dels": set(),
                "calls": set(),
            }
        }

        assert results == expected

        # REGRESSION
        # Test if "arg.first" and "arg.second" are in "gets"
        _ast = parse(
            """
            def fn(arg):
                return (arg.first + arg.second).some_property
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        expected = {
            fn_symbol: {
                "sets": set(),
                "gets": {
                    Name("arg.first", "arg"),
                    Name("arg.second", "arg"),
                    Name("@BinOp.some_property", "@BinOp"),
                },
                "dels": set(),
                "calls": set(),
            }
        }

        assert results == expected

        #
        # In Starred
        #
        _ast = parse(
            """
            def fn(arg):
                return call(*[arg.first + arg.second])
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        expected = {
            fn_symbol: {
                "sets": set(),
                "gets": {
                    Name("arg.first", "arg"),
                    Name("arg.second", "arg"),
                    Name("*@List", "@List"),
                },
                "dels": set(),
                "calls": {
                    Call(
                        name="call()",
                        args=CallArguments(args=("*@List",), kwargs={}),
                        target=None,
                    ),
                },
            }
        }

        assert results == expected

        #
        # In Subscript
        #
        _ast = parse(
            """
            def fn(arg):
                return (arg.first + arg.second)["index"]
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        expected = {
            fn_symbol: {
                "sets": set(),
                "gets": {
                    Name("arg.first", "arg"),
                    Name("arg.second", "arg"),
                    Name("@BinOp[]", "@BinOp"),
                },
                "dels": set(),
                "calls": set(),
            }
        }

        assert results == expected

    def test_regression_gets_in_method_call(self, parse):
        # ALWAYS WORKED
        _ast = parse(
            """
            def fn(arg):
                return arg.attr
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        fn_symbol = Func(name="fn", interface=CallInterface(args=("arg",)))

        expected = {
            fn_symbol: {
                "sets": set(),
                "gets": {
                    Name("arg.attr", "arg"),
                },
                "dels": set(),
                "calls": set(),
            }
        }

        assert results == expected

        # ALWAYS WORKED
        _ast = parse(
            """
            def fn(arg):
                return arg.method()
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        expected = {
            fn_symbol: {
                "sets": set(),
                "gets": set(),
                "dels": set(),
                "calls": {
                    Call(
                        name="arg.method()",
                        args=CallArguments(args=(), kwargs=[]),
                        target=Name("arg"),
                    ),
                },
            }
        }

        assert results == expected

        # REGRESSION 1
        _ast = parse(
            """
            def fn(arg):
                return arg.attr.method()
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        expected = {
            fn_symbol: {
                "sets": set(),
                "gets": {
                    Name("arg.attr", "arg"),
                },
                "dels": set(),
                "calls": {
                    Call(
                        name="arg.attr.method()",
                        args=CallArguments(args=(), kwargs={}),
                        target=Name("arg"),
                    ),
                },
            }
        }

        assert results == expected

        # REGRESSION 2
        _ast = parse(
            """
            def fn(arg):
                return arg.a.b.c.d.method()
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        expected = {
            fn_symbol: {
                "sets": set(),
                "gets": {
                    Name("arg.a", "arg"),
                    Name("arg.a.b", "arg"),
                    Name("arg.a.b.c", "arg"),
                    Name("arg.a.b.c.d", "arg"),
                },
                "dels": set(),
                "calls": {
                    Call(
                        name="arg.a.b.c.d.method()",
                        args=CallArguments(args=(), kwargs={}),
                        target=Name("arg"),
                    ),
                },
            }
        }

        assert results == expected


class TestNamedTupleFromCall:
    # Test namedtuples constructed by calls to `collections.namedtuple`.
    # This failed at analyse, not simplification, but we should confirm that it passes
    # simplification nonetheless.

    @pytest.fixture(autouse=True)
    def _test_in_strict_mode(self, arguments) -> Iterator[None]:
        with arguments(is_strict=True):
            yield

    def test_call_with_positional_arguments(self, constant, parse):
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
            _ = generate_results_from_ir(file_ir, imports_ir={})

        point = Class(
            name="point",
            interface=CallInterface(args=("self", "x", "y")),
        )
        point_call = Call(
            name="point()",
            args=CallArguments(
                args=("@ReturnValue", constant("Str"), constant("Str")),
                kwargs={},
            ),
            target=point,
        )
        by_pos = Func(name="by_pos", interface=CallInterface(args=()))

        expected = {
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
        }

        assert file_ir._file_ir == expected
        assert _exit.call_count == 0

    def test_call_with_keyword_arguments(self, constant, parse):
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
            _ = generate_results_from_ir(file_ir, imports_ir={})

        point = Class(
            name="point",
            interface=CallInterface(args=("self", "x", "y")),
        )
        point_call = Call(
            name="point()",
            args=CallArguments(
                args=("@ReturnValue",),
                kwargs={"x": constant("Str"), "y": constant("Str")},
            ),
            target=point,
        )
        by_keyword = Func(name="by_keyword", interface=CallInterface(args=()))

        expected = {
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
        }

        assert file_ir._file_ir == expected
        assert _exit.call_count == 0

    def test_call_with_positional_and_keyword_arguments(self, constant, parse):
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
            _ = generate_results_from_ir(file_ir, imports_ir={})

        point = Class(
            name="point",
            interface=CallInterface(args=("self", "x", "y")),
        )
        point_call = Call(
            name="point()",
            args=CallArguments(
                args=("@ReturnValue", constant("Str")),
                kwargs={"y": constant("Str")},
            ),
            target=point,
        )
        by_mixture = Func(name="by_mixture", interface=CallInterface(args=()))

        expected = {
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
        }

        assert file_ir._file_ir == expected
        assert _exit.call_count == 0

    def test_locally_defined_named_tuple(self, constant, parse):
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
            _ = generate_results_from_ir(file_ir, imports_ir={})

        point = Class(
            name="point",
            interface=CallInterface(args=("self", "x", "y")),
        )
        point_call = Call(
            name="point()",
            args=CallArguments(
                args=("@ReturnValue", constant("Str")),
                kwargs={"y": constant("Str")},
            ),
            target=point,
        )
        fn = Func(name="fn", interface=CallInterface(args=()))

        expected = {
            fn: {
                "gets": set(),
                "sets": set(),
                "dels": set(),
                "calls": {point_call},
            },
        }

        # `point` is defined as a local callable, which is no yet supported, thus this
        # should fail in strict mode.
        assert file_ir._file_ir == expected
        assert _exit.call_count == 1

    def test_call_with_space_delimited_string_argument(self, constant, parse):
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
            _ = generate_results_from_ir(file_ir, imports_ir={})

        point = Class(
            name="point",
            interface=CallInterface(args=("self", "x", "y")),
        )
        point_call = Call(
            name="point()",
            args=CallArguments(
                args=("@ReturnValue", constant("Str")),
                kwargs={"y": constant("Str")},
            ),
            target=point,
        )
        my_function = Func(name="my_function", interface=CallInterface(args=()))

        expected = {
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
        }

        assert file_ir._file_ir == expected
        assert _exit.call_count == 0


class TestNamedTupleFromInheritance:
    # Test namedtuples constructed by inheriting from `typing.NamedTuple`.
    # This previously had a fatal error at simplification.

    @pytest.fixture(autouse=True)
    def _test_in_strict_mode(self, arguments) -> Iterator[None]:
        with arguments(is_strict=True):
            yield

    def test_call_with_positional_arguments(self, constant, parse):
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
            _ = generate_results_from_ir(file_ir, imports_ir={})

        point = Class(
            name="Point",
            interface=CallInterface(args=("self", "x", "y")),
        )
        point_call = Call(
            "Point()",
            args=CallArguments(
                args=("@ReturnValue", constant("Str"), constant("str")),
                kwargs={},
            ),
            target=point,
        )
        by_pos = Func(name="by_pos", interface=CallInterface(args=()))

        expected = {
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
        }

        assert file_ir._file_ir == expected
        assert _exit.call_count == 0

    def test_call_with_keyword_arguments(self, constant, parse):
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
            _ = generate_results_from_ir(file_ir, imports_ir={})

        point = Class(
            name="Point",
            interface=CallInterface(args=("self", "x", "y")),
        )
        point_call = Call(
            name="Point()",
            args=CallArguments(
                args=("@ReturnValue",),
                kwargs={"x": constant("Str"), "y": constant("Str")},
            ),
            target=point,
        )
        by_keyword = Func(name="by_keyword", interface=CallInterface(args=()))

        expected = {
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
        }

        assert file_ir._file_ir == expected
        assert _exit.call_count == 0

    def test_call_with_positional_and_keyword_arguments(self, constant, parse):
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
            _ = generate_results_from_ir(file_ir, imports_ir={})

        point = Class(
            name="Point",
            interface=CallInterface(args=("self", "x", "y")),
        )
        point_call = Call(
            name="Point()",
            args=CallArguments(
                args=("@ReturnValue", constant("Str")),
                kwargs={"y": constant("Str")},
            ),
            target=point,
        )
        by_mixture = Func(name="by_mixture", interface=CallInterface(args=()))

        expected = {
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
        }

        assert file_ir._file_ir == expected
        assert _exit.call_count == 0


class TestRattrConstantInNameableOnCheckForNamedTuple:
    """
    Brief:
    On checking if there is a named-tuple in the right-hand side of an expression,
    when the right hand side is a non-safely nameable expression an error is given.

    Introduced: 0.1.7
    Fixed: 0.1.8
    """

    def test_safely_determine_rhs_name_on_namedtuple_check(self, parse, constant):
        _ast = parse(
            """
            def my_function(foobar, info=None):
                i_cause_the_error = "_".join(info.parts)
            """
        )

        with mock.patch("sys.exit") as _exit:
            file_ir = FileAnalyser(_ast, compile_root_context(_ast)).analyse()
            _ = generate_results_from_ir(file_ir, imports_ir={})

        my_function = Func(
            name="my_function",
            interface=CallInterface(args=("foobar", "info")),
        )
        string_join = f"{constant('@Str')}.join()"
        string_join_call = Call(
            string_join,
            args=CallArguments(args=("info.parts",), kwargs={}),
        )

        expected_file_ir = {
            my_function: {
                "gets": {Name("info.parts", basename="info")},
                "sets": {Name("i_cause_the_error")},
                "dels": set(),
                "calls": {string_join_call},
            }
        }

        assert not _exit.called
        assert file_ir._file_ir == expected_file_ir


@pytest.mark.usefixtures("run_in_strict_mode")
class TestGeneratorAndComprehensionsAreDeeplyVisited:
    def test_generator_expression(
        self,
        analyse_single_file: Callable[[str], tuple[FileIR, FileResults]],
        root_context_with: Callable[[list[Symbol]], Context],
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

        stdout, _ = capfd.readouterr()
        assert helpers.stdout_matches(stdout, [])

        symbols = {
            "fn": Func("fn", ["xss"]),
        }

        assert file_ir.context == root_context_with(symbols.values())
        assert file_ir._file_ir == {
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
        }
        assert file_results == {
            "fn": {
                "gets": {"_x", "_x.is_usable", "xs", "xss", "x.other_attr", "x.attr"},
                "sets": {"_x", "xs", "x"},
                "dels": set(),
                "calls": set(),
            }
        }

    def test_simple_ternary_in_generator_expression(
        self,
        analyse_single_file: Callable[[str], tuple[FileIR, FileResults]],
        root_context_with: Callable[[list[Symbol]], Context],
        capfd: pytest.CaptureFixture[str],
        builtin: Callable[[str], Builtin],
    ):
        file_ir, file_results = analyse_single_file(
            """
            def fn(foos):
                return any(foo.bar if foo.bar else foo.baz for foo in foos)
            """
        )

        stdout, _ = capfd.readouterr()
        assert helpers.stdout_matches(stdout, [])

        symbols = {
            "fn": Func("fn", ["foos"]),
        }

        assert file_ir.context == root_context_with(symbols.values())
        assert file_ir._file_ir == {
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
                    Call("any()", ["@GeneratorExp"], {}, target=builtin("any")),
                },
            }
        }
        assert file_results == {
            "fn": {
                "gets": {"foo.bar", "foo.baz", "foos"},
                "sets": {"foo"},
                "dels": set(),
                "calls": {"any()"},
            }
        }

    def test_simple_walrus_in_generator_expression(
        self,
        analyse_single_file: Callable[[str], tuple[FileIR, FileResults]],
        root_context_with: Callable[[list[Symbol]], Context],
        capfd: pytest.CaptureFixture[str],
        builtin: Callable[[str], Builtin],
    ):
        file_ir, file_results = analyse_single_file(
            """
            def fn(foos):
                return any(sum(baz) for foo in foos if (baz := foo.bars))
            """
        )

        stdout, _ = capfd.readouterr()
        assert helpers.stdout_matches(stdout, [])

        symbols = {
            "fn": Func("fn", ["foos"]),
        }

        assert file_ir.context == root_context_with(symbols.values())
        assert file_ir._file_ir == {
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
                    Call("any()", ["@GeneratorExp"], {}, target=builtin("any")),
                    Call("sum()", ["baz"], {}, target=builtin("sum")),
                },
            }
        }
        assert file_results == {
            "fn": {
                "gets": {"foo.bars", "foos", "baz"},
                "sets": {"foo", "baz"},
                "dels": set(),
                "calls": {"any()", "sum()"},
            }
        }

    def test_nested_ternary_in_generator_expression(
        self,
        analyse_single_file: Callable[[str], tuple[FileIR, FileResults]],
        root_context_with: Callable[[list[Symbol]], Context],
        capfd: pytest.CaptureFixture[str],
        builtin: Callable[[str], Builtin],
    ):
        file_ir, file_results = analyse_single_file(
            """
            def fn(foos):
                return any(f for f in [foo.bar if foo.bar else foo.baz for foo in foos])
            """
        )

        stdout, _ = capfd.readouterr()
        assert helpers.stdout_matches(stdout, [])

        symbols = {
            "fn": Func("fn", ["foos"]),
        }

        assert file_ir.context == root_context_with(symbols.values())
        assert file_ir._file_ir == {
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
                    Call("any()", ["@GeneratorExp"], {}, target=builtin("any")),
                },
            }
        }
        assert file_results == {
            "fn": {
                "gets": {"foo.bar", "foo.baz", "foos", "f"},
                "sets": {"foo", "f"},
                "dels": set(),
                "calls": {"any()"},
            }
        }

    def test_nested_walrus_in_generator_expression(
        self,
        analyse_single_file: Callable[[str], tuple[FileIR, FileResults]],
        root_context_with: Callable[[list[Symbol]], Context],
        capfd: pytest.CaptureFixture[str],
        builtin: Callable[[str], Builtin],
    ):
        file_ir, file_results = analyse_single_file(
            """
            def fn(foos):
                return any(sum(b) for b in [baz for foo in foos if (baz := foo.bars)])
            """
        )

        stdout, _ = capfd.readouterr()
        assert helpers.stdout_matches(stdout, [])

        symbols = {
            "fn": Func("fn", ["foos"]),
        }

        assert file_ir.context == root_context_with(symbols.values())
        assert file_ir._file_ir == {
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
                    Call("any()", ["@GeneratorExp"], {}, target=builtin("any")),
                    Call("sum()", ["b"], {}, target=builtin("sum")),
                },
            }
        }
        assert file_results == {
            "fn": {
                "gets": {"foo.bars", "foos", "baz", "b"},
                "sets": {"foo", "baz", "b"},
                "dels": set(),
                "calls": {"any()", "sum()"},
            }
        }


@pytest.mark.usefixtures("run_in_permissive_mode")
class TestGeneratorAndComprehensionsAreDeeplyVisitedPermissive:
    def test_deeply_nested_comprehensions(
        self,
        analyse_single_file: Callable[[str], tuple[FileIR, FileResults]],
        root_context_with: Callable[[list[Symbol]], Context],
        builtin: Callable[[str], Builtin],
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

        stdout, _ = capfd.readouterr()
        assert helpers.stdout_matches(
            stdout,
            [
                helpers.as_error(
                    "unable to resolve call to 'p', likely a procedural parameter"
                ),
            ],
        )

        symbols = {
            "fn": Func("fn", ["data"]),
        }

        assert file_ir.context == root_context_with(symbols.values())
        assert file_ir._file_ir == {
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
                    Call("any()", ["@GeneratorExp"], {}, builtin("any")),
                    Call("p()", [], {}, Name("p")),
                    Call("isinstance()", ["p", "Callable"], {}, builtin("isinstance")),
                    Call("foo.as_dict()", [], {}, Name("foo")),
                },
            }
        }
        assert file_results == {
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
