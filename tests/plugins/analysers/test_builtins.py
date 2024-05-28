from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from rattr.analyser.file import FileAnalyser
from rattr.models.context import Context, compile_root_context
from rattr.models.ir import FileIr
from rattr.models.symbol import Call, CallArguments, CallInterface, Func, Name
from rattr.plugins import plugins
from rattr.plugins.analysers.builtins import SortedAnalyser

if TYPE_CHECKING:
    from tests.shared import MakeSymbolTableFn, ParseFn


class TestCustomFunctionAnalysers:
    @pytest.fixture(autouse=True)
    def apply_plugins(self):
        plugins.register(SortedAnalyser())

    def test_sorted_no_key(self, parse: ParseFn, make_symbol_table: MakeSymbolTableFn):
        _ast = parse(
            """
            def a_func(arg):
                sorted(arg)
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table([a_func], include_root_symbols=True),
            ),
            file_ir={
                a_func: {
                    "gets": {
                        Name("arg"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

    def test_sorted_with_constant_key(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))

        # Literal
        _ast = parse(
            """
            def a_func(arg):
                sorted(arg, key=1)
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table([a_func], include_root_symbols=True),
            ),
            file_ir={
                a_func: {
                    "gets": {
                        Name("arg"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

        # Attribute
        _ast = parse(
            """
            def a_func(arg):
                sorted(arg, key=arg.attr)
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table([a_func], include_root_symbols=True),
            ),
            file_ir={
                a_func: {
                    "gets": {
                        Name("arg"),
                        Name("arg.attr", "arg"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

    def test_sorted_key_is_callable(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        # Via lambda
        _ast = parse(
            """
            def a_func(arg):
                sorted(arg, key=lambda a: key_func(a))

            def key_func(a):
                return a.b
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        key_func = Func(name="key_func", interface=CallInterface(args=("a",)))
        key_func_call = Call(
            name="key_func",
            args=CallArguments(args=("a",), kwargs={}),
            target=key_func,
        )

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table(
                    [
                        a_func,
                        key_func,
                    ],
                    include_root_symbols=True,
                ),
            ),
            file_ir={
                a_func: {
                    "gets": {
                        Name("arg"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": {key_func_call},
                },
                key_func: {
                    "gets": {
                        Name("a.b", "a"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_sorted_key_is_attribute_or_element(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))

        # Attribute
        _ast = parse(
            """
            def a_func(arg):
                sorted(arg, key=lambda a: a.attr)
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table([a_func], include_root_symbols=True),
            ),
            file_ir={
                a_func: {
                    "gets": {
                        Name("arg"),
                        Name("arg.attr", "arg"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

        # Element
        _ast = parse(
            """
            def a_func(arg):
                sorted(arg, key=lambda a: a[0])
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table([a_func], include_root_symbols=True),
            ),
            file_ir={
                a_func: {
                    "gets": {
                        Name("arg"),
                        Name("arg[]", "arg"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

        # Complex
        _ast = parse(
            """
            def a_func(arg):
                sorted(arg, key=lambda a: a[0].attr)
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table([a_func], include_root_symbols=True),
            ),
            file_ir={
                a_func: {
                    "gets": {
                        Name("arg"),
                        Name("arg[].attr", "arg"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected
