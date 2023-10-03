"""Run the full analyser (in single file mode) on a snippet of code.

This should test source code snippets containing the use of a single feature, to ensure
that when run through the full analyser the end results and IR are as expected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

import tests.helpers as helpers
from rattr.analyser.context.symbol import Builtin, Call, Func, Name, Symbol

if TYPE_CHECKING:
    from typing import Callable

    from rattr.analyser.context import Context
    from rattr.analyser.types import FileIR, FileResults


class TestGeneratorExpression:
    def test_simple_generator_expression(
        self,
        analyse_single_file: Callable[[str], tuple[FileIR, FileResults]],
        root_context_with: Callable[[list[Symbol]], Context],
        builtin: Callable[[str], Builtin],
        capfd: pytest.CaptureFixture[str],
    ):
        file_ir, file_results = analyse_single_file(
            """
            def sum_attrs(xs):
                return sum(x.attr for x in xs)
            """
        )

        stdout, _ = capfd.readouterr()
        assert helpers.stdout_matches(stdout, [])

        symbols = {
            "sum_attrs": Func("sum_attrs", ["xs"]),
        }

        assert file_ir.context == root_context_with(symbols.values())
        assert file_ir._file_ir == {
            symbols["sum_attrs"]: {
                "gets": {
                    Name("xs"),
                    Name("x.attr", "x"),
                },
                "sets": {
                    Name("x"),
                },
                "dels": set(),
                "calls": {
                    Call("sum()", ["@GeneratorExp"], {}, target=builtin("sum")),
                },
            }
        }
        assert file_results == {
            "sum_attrs": {
                "gets": {"xs", "x.attr"},
                "sets": {"x"},
                "dels": set(),
                "calls": {"sum()"},
            }
        }

    def test_generator_expression_with_ifs(
        self,
        analyse_single_file: Callable[[str], tuple[FileIR, FileResults]],
        root_context_with: Callable[[list[Symbol]], Context],
        builtin: Callable[[str], Builtin],
        capfd: pytest.CaptureFixture[str],
    ):
        file_ir, file_results = analyse_single_file(
            """
            def sum_attrs(xs):
                return sum(
                    x.attr
                    for x in xs
                    if x.if_attr > 1
                    if x.another_attr == value
                )
            """
        )

        stdout, _ = capfd.readouterr()
        assert helpers.stdout_matches(
            stdout,
            [helpers.as_warning("'value' potentially undefined")],
        )

        symbols = {
            "sum_attrs": Func("sum_attrs", ["xs"]),
        }

        assert file_ir.context == root_context_with(symbols.values())
        assert file_ir._file_ir == {
            symbols["sum_attrs"]: {
                "gets": {
                    Name("xs"),
                    Name("x.attr", "x"),
                    Name("x.if_attr", "x"),
                    Name("x.another_attr", "x"),
                    Name("value"),
                },
                "sets": {
                    Name("x"),
                },
                "dels": set(),
                "calls": {
                    Call("sum()", ["@GeneratorExp"], {}, target=builtin("sum")),
                },
            }
        }
        assert file_results == {
            "sum_attrs": {
                "gets": {"xs", "x.attr", "x.if_attr", "x.another_attr", "value"},
                "sets": {"x"},
                "dels": set(),
                "calls": {"sum()"},
            }
        }

    def test_generator_with_unbinding(
        self,
        analyse_single_file: Callable[[str], tuple[FileIR, FileResults]],
        root_context_with: Callable[[list[Symbol]], Context],
        builtin: Callable[[str], Builtin],
        capfd: pytest.CaptureFixture[str],
    ):
        file_ir, file_results = analyse_single_file(
            """
            def sum_attrs(xs, target):
                return sum(
                    x.attr
                    for x in xs
                    if x.if_attr > target.if_attr
                )

            def caller(ys, my_target):
                return sum_attrs(ys, my_target)
            """
        )

        stdout, _ = capfd.readouterr()
        assert helpers.stdout_matches(stdout, [])

        symbols = {
            "sum_attrs": Func("sum_attrs", ["xs", "target"]),
            "caller": Func("caller", ["ys", "my_target"]),
        }

        assert file_ir.context == root_context_with(symbols.values())
        assert file_ir._file_ir == {
            symbols["sum_attrs"]: {
                "gets": {
                    Name("xs"),
                    Name("x.attr", "x"),
                    Name("x.if_attr", "x"),
                    Name("target.if_attr", "target"),
                },
                "sets": {
                    Name("x"),
                },
                "dels": set(),
                "calls": {
                    Call("sum()", ["@GeneratorExp"], {}, target=builtin("sum")),
                },
            },
            symbols["caller"]: {
                "gets": {
                    Name("ys"),
                    Name("my_target"),
                },
                "sets": set(),
                "dels": set(),
                "calls": {
                    Call(
                        "sum_attrs()",
                        ["ys", "my_target"],
                        {},
                        target=symbols["sum_attrs"],
                    ),
                },
            },
        }
        assert file_results == {
            "sum_attrs": {
                "gets": {"xs", "x.attr", "target.if_attr", "x.if_attr"},
                "sets": {"x"},
                "dels": set(),
                "calls": {"sum()"},
            },
            "caller": {
                "gets": {"my_target.if_attr", "x.if_attr", "my_target", "ys", "x.attr"},
                "sets": {"x"},
                "dels": set(),
                "calls": {"sum_attrs()"},
            },
        }

    def test_with_multiple_generators(
        self,
        analyse_single_file: Callable[[str], tuple[FileIR, FileResults]],
        root_context_with: Callable[[list[Symbol]], Context],
        builtin: Callable[[str], Builtin],
        capfd: pytest.CaptureFixture[str],
    ):
        file_ir, file_results = analyse_single_file(
            """
            def sum_attrs(wrapper):
                return sum(
                    x.a
                    for inner in wrapper.xss
                    if wrapper.xs > wrapper.xs_threshold
                    for x in inner.xs
                    if inner.x_value > inner.x_threshold
                )
            """
        )

        stdout, _ = capfd.readouterr()
        assert helpers.stdout_matches(stdout, [])

        symbols = {
            "sum_attrs": Func("sum_attrs", ["wrapper"]),
        }

        assert file_ir.context == root_context_with(symbols.values())
        assert file_ir._file_ir == {
            symbols["sum_attrs"]: {
                "gets": {
                    Name("x.a", "x"),
                    Name("wrapper.xss", "wrapper"),
                    Name("wrapper.xs", "wrapper"),
                    Name("wrapper.xs_threshold", "wrapper"),
                    Name("inner.xs", "inner"),
                    Name("inner.x_value", "inner"),
                    Name("inner.x_threshold", "inner"),
                },
                "sets": {
                    Name("inner"),
                    Name("x"),
                },
                "dels": set(),
                "calls": {
                    Call("sum()", ["@GeneratorExp"], {}, target=builtin("sum")),
                },
            }
        }
        assert file_results == {
            "sum_attrs": {
                "gets": {
                    "inner.x_value",
                    "inner.x_threshold",
                    "wrapper.xs_threshold",
                    "inner.xs",
                    "x.a",
                    "wrapper.xss",
                    "wrapper.xs",
                },
                "sets": {"x", "inner"},
                "dels": set(),
                "calls": {"sum()"},
            }
        }
