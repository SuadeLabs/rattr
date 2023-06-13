"""Tests for module/file level features."""
from __future__ import annotations

from unittest import mock

import pytest

from rattr.analyser.context import RootContext
from rattr.analyser.context.symbol import Func, Name
from rattr.analyser.file import FileAnalyser


class TestModuleLevelStatements:
    def test_assignment(self, parse):
        _ast = parse(
            """
            one = 1
            one = 1
            two = 2
            """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        assert results == {}

    def test_typed_assignment(self, parse):
        _ast = parse(
            """
            one: int = 1
            one: int = 1
            two: int = 2
            """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        assert results == {}

    def test_augmented_assignment(self, parse):
        _ast = parse(
            """
            one += 1
            one += 1
            two += 2
            """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        assert results == {}

    @pytest.mark.py_3_8_plus()
    def test_walrus_operator(self, parse):
        _ast = parse(
            """
            x = (y := 1)
            x = (y := 2)
            """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        assert results == {}

    def test_multiple_assignment(self, parse):
        _ast = parse(
            """
            a, b = some_tuple
            x, y = 1, 2
            z = 3, 4
            """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        assert results == {}

    def test_lambda(self, parse):
        # Anonymous
        _ast = parse(
            """
            lambda *a, **k: a.attr
            """
        )
        with mock.patch("sys.exit") as _exit:
            FileAnalyser(_ast, RootContext(_ast)).analyse()

        # Named
        _ast = parse(
            """
            name = lambda *a, **k: a.attr
            """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("name", [], "a", "k"): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("a.attr", "a"),
                },
                "sets": set(),
            },
        }

        assert results == expected

    @pytest.mark.py_3_8_plus()
    def test_walrus_multiple_assignment(self, parse):
        # Walrus multi assign w/ lambda
        _ast = parse(
            """
            other = (alpha, beta := 1)
            other, another = (alpha, beta := 1)
            """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {}

        assert results == expected

    @pytest.mark.py_3_8_plus()
    def test_walrus_multiple_assignment_list(self, parse):
        # Walrus multi assign w/ lambda
        _ast = parse(
            """
            other = [alpha, beta := 1]
            other, another = [alpha, beta := 1]
            """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {}

        assert results == expected

    @pytest.mark.py_3_8_plus()
    def test_walrus_lambda(self, parse):
        # Walrus'd Lambda
        _ast = parse(
            """
            other = (name := lambda *a, **k: a.attr)
            """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("name", [], "a", "k"): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("a.attr", "a"),
                },
                "sets": set(),
            },
            Func("other", [], "a", "k"): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("a.attr", "a"),
                },
                "sets": set(),
            },
        }

        assert results == expected

    @pytest.mark.py_3_8_plus()
    def test_walrus_multiple_assignment_lambda(self, parse):
        # Walrus multi assign w/ lambda
        _ast = parse(
            """
            other = (alpha, beta := lambda *a, **k: a.attr)
            """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("beta", [], "a", "k"): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("a.attr", "a"),
                },
                "sets": set(),
            },
        }

        assert results == expected

    @pytest.mark.py_3_8_plus()
    def test_walrus_multiple_assignment_lambda_list(self, parse):
        # Walrus multi assign w/ lambda
        _ast = parse(
            """
            other = [alpha, beta := lambda *a, **k: a.attr]
            """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("beta", [], "a", "k"): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("a.attr", "a"),
                },
                "sets": set(),
            },
        }

        assert results == expected
