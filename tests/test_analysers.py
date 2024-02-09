"""Tests shared across multiple analysers."""
from __future__ import annotations

import attrs

from rattr.analyser.file import FileAnalyser
from rattr.models.context import compile_root_context
from rattr.models.symbol import Call, CallInterface, Func, Name


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
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        a_func_async = attrs.evolve(a_func, is_async=True)

        expected = {
            a_func: {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("arg.attr", "arg"),
                },
                "sets": set(),
            },
        }
        assert results.ir_as_dict() == expected

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
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        expected = {
            a_func_async: {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("arg.attr", "arg"),
                },
                "sets": set(),
            },
        }
        assert results.ir_as_dict() == expected

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
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        expected = {
            a_func_async: {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("arg.attr", "arg"),
                },
                "sets": set(),
            },
        }
        assert results.ir_as_dict() == expected

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
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        a_func_async = attrs.evolve(a_func, is_async=True)

        another_func = Func(name="another_func", interface=CallInterface(args=("arg",)))
        another_func_async = attrs.evolve(a_func, is_async=True)

        expected = {
            a_func: {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("arg.attr", "arg"),
                },
                "sets": set(),
            },
            another_func: {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("a"),
                    Name("b"),
                },
                "sets": set(),
            },
        }
        assert results.ir_as_dict() == expected

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
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        expected = {
            a_func_async: {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("arg.attr", "arg"),
                },
                "sets": set(),
            },
            another_func_async: {
                "calls": set(),
                "dels": set(),
                "gets": set(),
                "sets": set(),
            },
        }

        assert results.ir_as_dict() == expected

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
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        another_func = Func(name="another_func", interface=CallInterface(args=("arg",)))

        expected = {
            a_func: {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("arg.attr", "arg"),
                },
                "sets": set(),
            },
            another_func: {
                "calls": {Call("fn_a()", ["a", "a.attr"], {"key": "b.key"})},
                "dels": set(),
                "gets": {
                    Name("a.attr", "a"),
                    Name("*b.value", "b"),
                },
                "sets": set(),
            },
        }

        assert results.ir_as_dict() == expected
