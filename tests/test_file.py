"""Tests for module/file level features."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from rattr.analyser.file import FileAnalyser
from rattr.models.context import compile_root_context
from rattr.models.symbol import CallInterface, Func, Name

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests.shared import StateFn


@pytest.fixture(autouse=True)
def __set_current_file(state: StateFn) -> Iterator[None]:
    with state(current_file=Path(__file__)):
        yield


class TestModuleLevelStatements:
    def test_assignment(self, parse):
        _ast = parse(
            """
            one = 1
            one = 1
            two = 2
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        assert results.ir_as_dict() == {}

    def test_typed_assignment(self, parse):
        _ast = parse(
            """
            one: int = 1
            one: int = 1
            two: int = 2
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        assert results.ir_as_dict() == {}

    def test_augmented_assignment(self, parse):
        _ast = parse(
            """
            one += 1
            one += 1
            two += 2
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        assert results.ir_as_dict() == {}

    def test_walrus_operator(self, parse):
        _ast = parse(
            """
            x = (y := 1)
            x = (y := 2)
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        assert results.ir_as_dict() == {}

    def test_multiple_assignment(self, parse):
        _ast = parse(
            """
            a, b = some_tuple
            x, y = 1, 2
            z = 3, 4
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        assert results.ir_as_dict() == {}

    def test_lambda(self, parse):
        # Anonymous
        _ast = parse(
            """
            lambda *a, **k: a.attr
            """
        )
        with mock.patch("sys.exit") as _exit:
            FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        # Named
        _ast = parse(
            """
            name = lambda *a, **k: a.attr
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        name = Func(name="name", interface=CallInterface(vararg="a", kwarg="k"))

        expected = {
            name: {
                "calls": set(),
                "dels": set(),
                "gets": {Name("a.attr", "a")},
                "sets": set(),
            },
        }

        assert results.ir_as_dict() == expected

    def test_walrus_multiple_assignment(self, parse):
        # Walrus multi assign w/ lambda
        _ast = parse(
            """
            other = (alpha, beta := 1)
            other, another = (alpha, beta := 1)
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        assert results.ir_as_dict() == {}

    def test_walrus_multiple_assignment_list(self, parse):
        # Walrus multi assign w/ lambda
        _ast = parse(
            """
            other = [alpha, beta := 1]
            other, another = [alpha, beta := 1]
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        assert results.ir_as_dict() == {}

    def test_walrus_lambda(self, parse):
        # Walrus'd Lambda
        _ast = parse(
            """
            other = (name := lambda *a, **k: a.attr)
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        name = Func(name="name", interface=CallInterface(vararg="a", kwarg="k"))
        other = Func(name="other", interface=CallInterface(vararg="a", kwarg="k"))

        expected = {
            name: {
                "calls": set(),
                "dels": set(),
                "gets": {Name("a.attr", "a")},
                "sets": set(),
            },
            other: {
                "calls": set(),
                "dels": set(),
                "gets": {Name("a.attr", "a")},
                "sets": set(),
            },
        }

        assert results.ir_as_dict() == expected

    def test_walrus_multiple_assignment_lambda(self, parse):
        # Walrus multi assign w/ lambda
        _ast = parse(
            """
            other = (alpha, beta := lambda *a, **k: a.attr)
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        beta = Func(name="beta", interface=CallInterface(vararg="a", kwarg="k"))

        expected = {
            beta: {
                "calls": set(),
                "dels": set(),
                "gets": {Name("a.attr", "a")},
                "sets": set(),
            },
        }

        assert results.ir_as_dict() == expected

    def test_walrus_multiple_assignment_lambda_list(self, parse):
        # Walrus multi assign w/ lambda
        _ast = parse(
            """
            other = [alpha, beta := lambda *a, **k: a.attr]
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        beta = Func(name="beta", interface=CallInterface(vararg="a", kwarg="k"))

        expected = {
            beta: {
                "calls": set(),
                "dels": set(),
                "gets": {Name("a.attr", "a")},
                "sets": set(),
            },
        }

        assert results.ir_as_dict() == expected
