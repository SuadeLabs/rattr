"""Tests shared across multiple analysers."""
from __future__ import annotations

from rattr.analyser.context import RootContext
from rattr.analyser.context.symbol import Call, Func, Name
from rattr.analyser.file import FileAnalyser


class TestAnnotations:
    def test_rattr_ignore(self, parse):
        # FunctionDef
        _ast = parse(
            """
            def a_func(arg):
                return arg.attr

            @rattr_ignore
            def another_func(arg):
                return arg.another_attr
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("arg.attr", "arg"),
                },
                "sets": set(),
            },
        }

        assert results == expected

        # AsyncFunctionDef
        _ast = parse(
            """
            async def a_func(arg):
                return arg.attr

            @rattr_ignore
            async def another_func(arg):
                return arg.another_attr
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None, is_async=True): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("arg.attr", "arg"),
                },
                "sets": set(),
            },
        }

        assert results == expected

        # ClassDef
        # AsyncFunctionDef
        _ast = parse(
            """
            async def a_func(arg):
                return arg.attr

            @rattr_ignore
            class SomeClass:
                def __init__(self, a):
                    self.a = a
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None, is_async=True): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("arg.attr", "arg"),
                },
                "sets": set(),
            },
        }

        assert results == expected

    def test_rattr_results(self, parse):
        # FunctionDef
        # Use incorrect results to show override is working
        _ast = parse(
            """
            def a_func(arg):
                return arg.attr

            @rattr_results(gets={"a", "b"})
            def another_func(arg):
                return arg.another_attr
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("arg.attr", "arg"),
                },
                "sets": set(),
            },
            Func("another_func", ["arg"], None, None): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("a"),
                    Name("b"),
                },
                "sets": set(),
            },
        }

        assert results == expected

        # AsyncFunctionDef
        # Use incorrect results to show override is working
        _ast = parse(
            """
            async def a_func(arg):
                return arg.attr

            @rattr_results()
            async def another_func(arg):
                return arg.another_attr
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None, is_async=True): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("arg.attr", "arg"),
                },
                "sets": set(),
            },
            Func("another_func", ["arg"], None, None, is_async=True): {
                "calls": set(),
                "dels": set(),
                "gets": set(),
                "sets": set(),
            },
        }

        assert results == expected

        # ClassDef
        # TODO When classes added

    def test_rattr_results_complex(self, parse):
        # FunctionDef
        # Use incorrect results to show override is working
        _ast = parse(
            """
            def a_func(arg):
                return arg.attr

            @rattr_results(
                gets={"a.attr", "*b.value"},
                calls=[
                    ("fn_a()", (["a", "a.attr"], {"key": "b.key"}))
                ]
            )
            def another_func(arg):
                return arg.another_attr
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("arg.attr", "arg"),
                },
                "sets": set(),
            },
            Func("another_func", ["arg"], None, None): {
                "calls": {Call("fn_a()", ["a", "a.attr"], {"key": "b.key"})},
                "dels": set(),
                "gets": {
                    Name("a.attr", "a"),
                    Name("*b.value", "b"),
                },
                "sets": set(),
            },
        }

        print(results)
        assert results == expected
