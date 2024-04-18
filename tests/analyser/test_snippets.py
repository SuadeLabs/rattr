"""Run the full analyser (in single file mode) on a snippet of code.

This should test source code snippets containing the use of a single feature, to ensure
that when run through the full analyser the end results and IR are as expected.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import tests.helpers as helpers
from rattr.models.ir import FileIr
from rattr.models.results import FileResults
from rattr.models.symbol import (
    Builtin,
    Call,
    CallArguments,
    CallInterface,
    Func,
    Name,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from tests.shared import ArgumentsFn, MakeRootContextFn, StateFn


@pytest.fixture(autouse=True)
def __set_current_file(state: StateFn) -> Iterator[None]:
    with state(current_file=Path("my_test_file.py")):
        yield


@pytest.fixture(autouse=True)
def __set_warning_level(arguments: ArgumentsFn) -> Iterator[None]:
    with arguments(_warning_level="all"):
        yield


class TestGeneratorExpession:
    def test_simple_generator_expression(
        self,
        analyse_single_file: Callable[[str], tuple[FileIr, FileResults]],
        make_root_context: MakeRootContextFn,
        capfd: pytest.CaptureFixture[str],
    ):
        file_ir, file_results = analyse_single_file(
            """
            def sum_attrs(xs):
                return sum(x.attr for x in xs)
            """
        )

        _, stderr = capfd.readouterr()
        assert helpers.stdout_matches(stderr, [])

        sum_attrs_symbol = Func("sum_attrs", interface=CallInterface(args=("xs",)))
        expected_file_ir = FileIr(
            context=make_root_context([sum_attrs_symbol], include_root_symbols=True),
            file_ir={
                sum_attrs_symbol: {
                    "gets": {
                        Name("xs"),
                        Name("x.attr", "x"),
                    },
                    "sets": {
                        Name("x"),
                    },
                    "dels": set(),
                    "calls": {
                        Call(
                            name="sum",
                            args=CallArguments(args=("@GeneratorExp",)),
                            target=Builtin(name="sum"),
                        )
                    },
                }
            },
        )
        expected_file_results = FileResults(
            {
                sum_attrs_symbol.id: {
                    "gets": {"xs", "x.attr"},
                    "sets": {"x"},
                    "dels": set(),
                    "calls": {"sum()"},
                }
            }
        )

        assert file_ir == expected_file_ir
        assert file_results == expected_file_results

    def test_generator_expression_with_ifs(
        self,
        analyse_single_file: Callable[[str], tuple[FileIr, FileResults]],
        make_root_context: MakeRootContextFn,
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

        _, stderr = capfd.readouterr()
        assert helpers.stderr_matches(
            stderr,
            [helpers.as_warning("'value' potentially undefined")],
        )

        sum_attrs_symbol = Func("sum_attrs", interface=CallInterface(args=("xs",)))
        expected_file_ir = FileIr(
            context=make_root_context([sum_attrs_symbol], include_root_symbols=True),
            file_ir={
                sum_attrs_symbol: {
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
                        Call(
                            name="sum",
                            args=CallArguments(args=("@GeneratorExp",)),
                            target=Builtin(name="sum"),
                        )
                    },
                }
            },
        )
        expected_file_results = FileResults(
            {
                sum_attrs_symbol.id: {
                    "gets": {"xs", "x.attr", "x.if_attr", "x.another_attr", "value"},
                    "sets": {"x"},
                    "dels": set(),
                    "calls": {"sum()"},
                }
            }
        )

        assert file_ir == expected_file_ir
        assert file_results == expected_file_results

    def test_generator_with_unbinding(
        self,
        analyse_single_file: Callable[[str], tuple[FileIr, FileResults]],
        make_root_context: MakeRootContextFn,
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

        _, stderr = capfd.readouterr()
        assert helpers.stdout_matches(stderr, [])

        symbols = {
            "sum_attrs": Func(
                "sum_attrs",
                interface=CallInterface(args=("xs", "target")),
            ),
            "caller": Func("caller", interface=CallInterface(args=("ys", "my_target"))),
        }
        expected_file_ir = FileIr(
            context=make_root_context(symbols.values(), include_root_symbols=True),
            file_ir={
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
                        Call(
                            "sum()",
                            args=CallArguments(args=("@GeneratorExp",)),
                            target=builtin("sum"),
                        ),
                    },
                },
                symbols["caller"]: {
                    "gets": {
                        Name("ys"),
                        Name("my_target"),
                        Name("my_target.if_attr", "my_target"),
                        Name("x.attr", "x"),
                        Name("x.if_attr", "x"),
                    },
                    "sets": {
                        Name("x"),
                    },
                    "dels": set(),
                    "calls": {
                        Call(
                            "sum_attrs()",
                            args=CallArguments(args=("ys", "my_target")),
                            target=symbols["sum_attrs"],
                        ),
                    },
                },
            },
        )
        expected_file_results = FileResults(
            {
                "sum_attrs": {
                    "gets": {"xs", "x.attr", "target.if_attr", "x.if_attr"},
                    "sets": {"x"},
                    "dels": set(),
                    "calls": {"sum()"},
                },
                "caller": {
                    "gets": {
                        "my_target.if_attr",
                        "x.if_attr",
                        "my_target",
                        "ys",
                        "x.attr",
                    },
                    "sets": {"x"},
                    "dels": set(),
                    "calls": {"sum_attrs()"},
                },
            }
        )

        assert file_ir == expected_file_ir
        assert file_results == expected_file_results

    def test_with_multiple_generators(
        self,
        analyse_single_file: Callable[[str], tuple[FileIr, FileResults]],
        make_root_context: MakeRootContextFn,
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

        _, stderr = capfd.readouterr()
        assert helpers.stdout_matches(stderr, [])

        symbols = {
            "sum_attrs": Func("sum_attrs", interface=CallInterface(args=("wrapper",))),
        }
        expected_file_ir = FileIr(
            context=make_root_context(symbols.values(), include_root_symbols=True),
            file_ir={
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
                        Call(
                            "sum()",
                            args=CallArguments(args=("@GeneratorExp",)),
                            target=builtin("sum"),
                        ),
                    },
                }
            },
        )
        expected_file_results = FileResults(
            {
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
        )

        assert file_ir == expected_file_ir
        assert file_results == expected_file_results
