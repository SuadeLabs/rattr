from __future__ import annotations

from typing import TYPE_CHECKING

from rattr.analyser.file import FileAnalyser
from rattr.models.context import Context, compile_root_context
from rattr.models.ir import FileIr
from rattr.models.symbol import (
    Builtin,
    Call,
    CallArguments,
    CallInterface,
    Func,
    Import,
    Name,
)

if TYPE_CHECKING:
    from tests.shared import MakeSymbolTableFn, ParseFn


class TestCustomCollectionsAnalysers:
    def test_defaultdict_no_factory(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        _ast = parse(
            """
            from collections import defaultdict

            def a_func(arg):
                d = defaultdict()
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        defaultdict_import = Import("defaultdict", "collections.defaultdict")
        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table(
                    [defaultdict_import, a_func],
                    include_root_symbols=True,
                ),
            ),
            file_ir={
                a_func: {
                    "gets": set(),
                    "sets": {Name("d")},
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

    def test_defaultdict_named_factory(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        _ast = parse(
            """
            from collections import defaultdict

            def a_func(arg):
                d = defaultdict(factory)

            def factory():
                return hello.results
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        defaultdict_import = Import("defaultdict", "collections.defaultdict")
        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        factory = Func(name="factory", interface=CallInterface(args=()))

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table(
                    [
                        defaultdict_import,
                        a_func,
                        factory,
                    ],
                    include_root_symbols=True,
                ),
            ),
            file_ir={
                a_func: {
                    "gets": set(),
                    "sets": {
                        Name("d"),
                    },
                    "dels": set(),
                    "calls": {Call("factory", args=CallArguments(), target=factory)},
                },
                factory: {
                    "gets": {
                        Name("hello.results", "hello"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_defaultdict_lambda_factory(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        defaultdict_import = Import("defaultdict", "collections.defaultdict")
        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))

        # Lambda to literal
        _ast = parse(
            """
            from collections import defaultdict

            def a_func(arg):
                d = defaultdict(lambda: 0)
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table(
                    [
                        defaultdict_import,
                        a_func,
                    ],
                    include_root_symbols=True,
                ),
            ),
            file_ir={
                a_func: {
                    "gets": set(),
                    "sets": {
                        Name("d"),
                    },
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

        # Lambda to attr
        _ast = parse(
            """
            from collections import defaultdict

            def a_func(arg):
                d = defaultdict(lambda: arg.attr)
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table(
                    [
                        defaultdict_import,
                        a_func,
                    ],
                    include_root_symbols=True,
                ),
            ),
            file_ir={
                a_func: {
                    "gets": {Name("arg.attr", "arg")},
                    "sets": {
                        Name("d"),
                    },
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

    def test_defaultdict_nested_factory(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        _ast = parse(
            """
            from collections import defaultdict

            def a_func(arg):
                d = defaultdict(defaultdict(list))
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        defaultdict_import = Import("defaultdict", "collections.defaultdict")
        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        list_builtin = Builtin("list")

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table(
                    [
                        defaultdict_import,
                        a_func,
                    ],
                    include_root_symbols=True,
                ),
            ),
            file_ir={
                a_func: {
                    "gets": set(),
                    "sets": {
                        Name("d"),
                    },
                    "dels": set(),
                    "calls": {Call("list", args=CallArguments(), target=list_builtin)},
                }
            },
        )

        assert results == expected
