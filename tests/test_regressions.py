from __future__ import annotations

from unittest import mock

import pytest

from rattr.analyser.context import (
    Builtin,
    Call,
    Class,
    Func,
    Name,
    RootContext,
)
from rattr.analyser.file import FileAnalyser
from rattr.analyser.results import generate_results_from_ir


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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("getter", ["a"], None, None): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("*a.b[]().c", "a"),
                },
                "sets": set(),
            },
            Func("setter", ["a"], None, None): {
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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("getter", ["a"], None, None): {
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
            Func("setter", ["a"], None, None): {
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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        max_symbol = Builtin("max", has_affect=False)
        expected = {
            Func("test_1", ["a"], None, None): {
                "calls": {
                    Call("@BinOp.method()", [], {}, None),
                    Call("max()", ["@BinOp.method()", constant("Num")], {}, max_symbol),
                },
                "dels": set(),
                "gets": set(),
                "sets": {
                    Name("a"),
                },
            },
            Func("test_2", ["a"], None, None): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("b"),
                    Name("@UnaryOp.c", "@UnaryOp"),
                },
                "sets": set(),
            },
        }

        print(results)
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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        fn_act = Func("act", ["on"], None, None)
        fn_a = Func("a_func", ["arg"], None, None)
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
                "calls": {Call("act()", ["arg.attr"], {}, target=fn_act)},
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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        bad_map = Func("bad_map", ["f", "target"], None, None)
        expected = {
            bad_map: {
                "sets": set(),
                "gets": {Name("target")},
                "dels": set(),
                "calls": {Call("f()", ["target"], {}, target=Name("f"))},
            }
        }

        assert results == expected

        output, _ = capfd.readouterr()
        assert "likely a procedural parameter" in output

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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        wrapper = Func("wrapper", [], None, None)
        actor = Func("actor", [], None, None)
        expected = {
            wrapper: {
                "sets": set(),
                "gets": {Name("inner")},
                "dels": set(),
                "calls": set(),
            },
            actor: {
                "sets": set(),
                "gets": set(),
                "dels": set(),
                "calls": {Call("wrapper()()", [], {}, target=wrapper)},
            },
        }

        assert results == expected

        output, _ = capfd.readouterr()
        assert "unable to resolve call result of call" in output

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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        fn_a = Func("fn_a", ["arg"], None, None)
        fn_b = Func("fn_b", ["arg"], None, None)
        bad = Func("bad", ["argument"], None, None)
        expected = {
            fn_a: {
                "sets": set(),
                "gets": {Name("arg.a", "arg")},
                "dels": set(),
                "calls": set(),
            },
            fn_b: {
                "sets": set(),
                "gets": {Name("arg.b", "arg")},
                "dels": set(),
                "calls": set(),
            },
            bad: {
                "sets": {
                    Name("accumulator"),
                    Name("f"),
                },
                "gets": {
                    Name("accumulator"),
                    Name("fn_a"),
                    Name("fn_b"),
                    Name("argument"),
                },
                "dels": set(),
                "calls": {Call("f()", ["argument"], {}, target=Name("f"))},
            },
        }

        assert results == expected

        output, _ = capfd.readouterr()
        assert "likely a procedural parameter" in output

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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("fn", [], None, None): {
                "sets": {
                    Name("list_of_tuples"),
                },
                "gets": {
                    Name("thing_one"),
                    Name("thing_two"),
                    Name("e"),
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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("fn", [], None, None): {
                "sets": {
                    Name("list_of_tuples"),
                },
                "gets": {
                    Name("thing"),
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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("fn", ["arg"], None, None): {
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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("fn", ["arg"], None, None): {
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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("fn", ["arg"], None, None): {
                "sets": set(),
                "gets": {
                    Name("arg.first", "arg"),
                    Name("arg.second", "arg"),
                    Name("*@List", "@List"),
                },
                "dels": set(),
                "calls": {
                    Call("call()", ["*@List"], {}, None),
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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("fn", ["arg"], None, None): {
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

        print(results)
        assert results == expected

    def test_regression_gets_in_method_call(self, parse):
        # ALWAYS WORKED
        _ast = parse(
            """
            def fn(arg):
                return arg.attr
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("fn", ["arg"], None, None): {
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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("fn", ["arg"], None, None): {
                "sets": set(),
                "gets": set(),
                "dels": set(),
                "calls": {
                    Call("arg.method()", [], {}, Name("arg")),
                },
            }
        }

        print(results)
        assert results == expected

        # REGRESSION 1
        _ast = parse(
            """
            def fn(arg):
                return arg.attr.method()
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("fn", ["arg"], None, None): {
                "sets": set(),
                "gets": {
                    Name("arg.attr", "arg"),
                },
                "dels": set(),
                "calls": {
                    Call("arg.attr.method()", [], {}, Name("arg")),
                },
            }
        }

        print(results)
        assert results == expected

        # REGRESSION 2
        _ast = parse(
            """
            def fn(arg):
                return arg.a.b.c.d.method()
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("fn", ["arg"], None, None): {
                "sets": set(),
                "gets": {
                    Name("arg.a", "arg"),
                    Name("arg.a.b", "arg"),
                    Name("arg.a.b.c", "arg"),
                    Name("arg.a.b.c.d", "arg"),
                },
                "dels": set(),
                "calls": {
                    Call("arg.a.b.c.d.method()", [], {}, Name("arg")),
                },
            }
        }

        print(results)
        assert results == expected


class TestNamedTupleFromCall:
    # Test namedtuples constructed by calls to `collections.namedtuple`.
    # This failed at analyse, not simplification, but we should confirm that it passes
    # simplification nonetheless.

    @pytest.fixture(autouse=True)
    def _set_current_file(self, config) -> None:
        with config("current_file", "my_test_file.py"):
            with config("strict", True):
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
            file_ir = FileAnalyser(_ast, RootContext(_ast)).analyse()
            _ = generate_results_from_ir(file_ir, imports_ir={})

        point = Class("point", args=["self", "x", "y"])
        point_call = Call(
            name="point()",
            args=["@ReturnValue", constant("Str"), constant("Str")],
            kwargs={},
            target=point,
        )
        expected = {
            point: {
                "gets": set(),
                "sets": set(),
                "dels": set(),
                "calls": set(),
            },
            Func("by_pos", []): {
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
            file_ir = FileAnalyser(_ast, RootContext(_ast)).analyse()
            _ = generate_results_from_ir(file_ir, imports_ir={})

        point = Class("point", args=["self", "x", "y"])
        point_call = Call(
            name="point()",
            args=["@ReturnValue"],
            kwargs={"x": constant("Str"), "y": constant("Str")},
            target=point,
        )
        expected = {
            point: {
                "gets": set(),
                "sets": set(),
                "dels": set(),
                "calls": set(),
            },
            Func("by_keyword", []): {
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
            file_ir = FileAnalyser(_ast, RootContext(_ast)).analyse()
            _ = generate_results_from_ir(file_ir, imports_ir={})

        point = Class("point", args=["self", "x", "y"])
        point_call = Call(
            name="point()",
            args=["@ReturnValue", constant("Str")],
            kwargs={"y": constant("Str")},
            target=point,
        )
        expected = {
            point: {
                "gets": set(),
                "sets": set(),
                "dels": set(),
                "calls": set(),
            },
            Func("by_mixture", []): {
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
            file_ir = FileAnalyser(_ast, RootContext(_ast)).analyse()
            _ = generate_results_from_ir(file_ir, imports_ir={})

        point = Class("point", args=["self", "x", "y"])
        point_call = Call(
            name="point()",
            args=["@ReturnValue", constant("Str")],
            kwargs={"y": constant("Str")},
            target=point,
        )
        expected = {
            Func("fn", []): {
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


class TestNamedTupleFromInheritance:
    # Test namedtuples constructed by inheriting from `typing.NamedTuple`.
    # This previously had a fatal error at simplification.

    @pytest.fixture(autouse=True)
    def _set_current_file(self, config) -> None:
        with config("current_file", "my_test_file.py"):
            with config("strict", True):
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
            file_ir = FileAnalyser(_ast, RootContext(_ast)).analyse()
            _ = generate_results_from_ir(file_ir, imports_ir={})

        point = Class(name="Point", args=["self", "x", "y"])
        point_call = Call(
            "Point()",
            args=["@ReturnValue", constant("Str"), constant("str")],
            kwargs={},
            target=point,
        )
        expected = {
            point: {
                "gets": set(),
                "sets": set(),
                "dels": set(),
                "calls": set(),
            },
            Func("by_pos", []): {
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
            file_ir = FileAnalyser(_ast, RootContext(_ast)).analyse()
            _ = generate_results_from_ir(file_ir, imports_ir={})

        point = Class(name="Point", args=["self", "x", "y"])
        point_call = Call(
            name="Point()",
            args=["@ReturnValue"],
            kwargs={"x": constant("Str"), "y": constant("Str")},
            target=point,
        )
        expected = {
            point: {
                "gets": set(),
                "sets": set(),
                "dels": set(),
                "calls": set(),
            },
            Func("by_keyword", []): {
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
            file_ir = FileAnalyser(_ast, RootContext(_ast)).analyse()
            _ = generate_results_from_ir(file_ir, imports_ir={})

        point = Class(name="Point", args=["self", "x", "y"])
        point_call = Call(
            name="Point()",
            args=["@ReturnValue", constant("Str")],
            kwargs={"y": constant("Str")},
            target=point,
        )
        expected = {
            point: {
                "gets": set(),
                "sets": set(),
                "dels": set(),
                "calls": set(),
            },
            Func("by_mixture", []): {
                "gets": set(),
                "sets": set(),
                "dels": set(),
                "calls": {point_call},
            },
        }

        assert file_ir._file_ir == expected
        assert _exit.call_count == 0
