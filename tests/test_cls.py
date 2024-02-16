from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from rattr.analyser.file import FileAnalyser
from rattr.models.context import Context, compile_root_context
from rattr.models.ir import FileIr
from rattr.models.symbol import (
    AnyCallInterface,
    Call,
    CallArguments,
    CallInterface,
    Class,
    Func,
    Import,
    Name,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests.shared import MakeSymbolTableFn, ParseFn, StateFn


@pytest.fixture(autouse=True)
def __set_current_file(state: StateFn) -> Iterator[None]:
    with state(current_file=Path(__file__)):
        yield


class TestClassAnalyser:
    def test_class_attributes(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        ast_ = parse(
            """
            class Numbers(NotARealEnum):
                One = 1
                Two = 2
                Three = 3
                Four, Five = 4, 5
            """
        )
        file_analyser = FileAnalyser(ast_, compile_root_context(ast_))
        file_analyser.analyse()

        expected = make_symbol_table(
            [
                Class(name="Numbers", interface=AnyCallInterface()),
                Name(name="Numbers.One", basename="Numbers"),
                Name(name="Numbers.Two", basename="Numbers"),
                Name(name="Numbers.Three", basename="Numbers"),
                Name(name="Numbers.Four", basename="Numbers"),
                Name(name="Numbers.Five", basename="Numbers"),
            ],
            include_root_symbols=True,
        )

        assert file_analyser.context.symbol_table == expected

    def test_class_initialiser(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        ast_ = parse(
            """
            class SomeClass:
                def __init__(self, some_arg):
                    self.whatever = some_arg.whatever
                    some_arg.good_number = 5    # 5 is a good number
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        some_class_symbol = Class(
            name="SomeClass",
            interface=CallInterface(args=("self", "some_arg")),
        )

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table(
                    [some_class_symbol], include_root_symbols=True
                ),
            ),
            file_ir={
                some_class_symbol: {
                    "sets": {
                        Name("self.whatever", "self"),
                        Name("some_arg.good_number", "some_arg"),
                    },
                    "gets": {
                        Name("some_arg.whatever", "some_arg"),
                    },
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

    def test_func_calls_class_initialiser(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        ast_ = parse(
            """
            def func(arg):
                return SomeClass(arg)

            class SomeClass:
                def __init__(self, some_arg):
                    self.whatever = some_arg.whatever
                    some_arg.good_number = 5    # 5 is a good number
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        func = Func(name="func", interface=CallInterface(args=("arg",)))
        cls = Class(
            name="SomeClass",
            interface=CallInterface(args=("self", "some_arg")),
        )
        cls_init_call = Call(
            name="SomeClass",
            args=CallArguments(
                args=(
                    "@ReturnValue",
                    "arg",
                ),
                kwargs={},
            ),
            target=cls,
        )

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table([func, cls], include_root_symbols=True),
            ),
            file_ir={
                func: {
                    "gets": {Name("arg")},
                    "sets": set(),
                    "dels": set(),
                    "calls": {cls_init_call},
                },
                cls: {
                    "gets": {
                        Name("some_arg.whatever", "some_arg"),
                    },
                    "sets": {
                        Name("self.whatever", "self"),
                        Name("some_arg.good_number", "some_arg"),
                    },
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_class_initialiser_calls_func(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        ast_ = parse(
            """
            def func(fn_arg):
                return fn_arg.some_attr

            class SomeClass:
                def __init__(self, some_arg):
                    self.a_thing = func(some_arg)
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        func = Func(name="func", interface=CallInterface(args=("fn_arg",)))
        cls = Class(
            name="SomeClass",
            interface=CallInterface(args=("self", "some_arg")),
        )
        func_call = Call(
            name="func",
            args=CallArguments(
                args=("some_arg",),
                kwargs={},
            ),
            target=func,
        )

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table([func, cls], include_root_symbols=True),
            ),
            file_ir={
                func: {
                    "sets": set(),
                    "gets": {Name("fn_arg.some_attr", "fn_arg")},
                    "dels": set(),
                    "calls": set(),
                },
                cls: {
                    "sets": {
                        Name("self.a_thing", "self"),
                    },
                    "gets": {
                        Name("some_arg"),
                    },
                    "dels": set(),
                    "calls": {func_call},
                },
            },
        )

        assert results == expected

    def test_staticmethod(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        ast_ = parse(
            """
            class SomeClass:
                @staticmethod
                def method(a, b):
                    a.attr = b.attr
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        cls = Class(name="SomeClass", interface=AnyCallInterface())
        method = Func(name="SomeClass.method", interface=CallInterface(args=("a", "b")))

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table(
                    [
                        cls,
                        method,
                    ],
                    include_root_symbols=True,
                ),
            ),
            file_ir={
                method: {
                    "sets": {Name("a.attr", "a")},
                    "gets": {Name("b.attr", "b")},
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

    def test_staticmethod_and_init(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        # Static method in "mixed" class
        ast_ = parse(
            """
            class SomeClass:
                def __init__(self, arg):
                    self.attr = arg

                @staticmethod
                def method(a, b):
                    a.attr = b.attr
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        cls = Class(name="SomeClass", interface=CallInterface(args=("self", "arg")))
        method = Func(name="SomeClass.method", interface=CallInterface(args=("a", "b")))

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table(
                    [
                        cls,
                        method,
                    ],
                    include_root_symbols=True,
                ),
            ),
            file_ir={
                cls: {
                    "sets": {Name("self.attr", "self")},
                    "gets": {Name("arg")},
                    "dels": set(),
                    "calls": set(),
                },
                method: {
                    "sets": {Name("a.attr", "a")},
                    "gets": {Name("b.attr", "b")},
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_class_with_static_members(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        ast_ = parse(
            """
            class FibIter:
                N  = 0
                N_ = 1

                @staticmethod
                def next() -> int:
                    last = FibIter.N

                    FibIter.N  = FibIter.N_
                    FibIter.N_ = FibIter.N_ + last

                    return FibIter.N
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        cls = Class(name="FibIter", interface=AnyCallInterface())
        cls_n = Name(name="FibIter.N", basename="FibIter")
        cls_n_ = Name(name="FibIter.N_", basename="FibIter")
        cls_next = Func(name="FibIter.next", interface=CallInterface(args=()))

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table(
                    [
                        cls,
                        cls_n,
                        cls_n_,
                        cls_next,
                    ],
                    include_root_symbols=True,
                ),
            ),
            file_ir={
                cls_next: {
                    "sets": {
                        Name("last"),
                        Name("FibIter.N", "FibIter"),
                        Name("FibIter.N_", "FibIter"),
                    },
                    "gets": {
                        Name("last"),
                        Name("FibIter.N", "FibIter"),
                        Name("FibIter.N_", "FibIter"),
                    },
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

    def test_enum_by_explicit_import(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        ast_ = parse(
            """
            from enum import Enum

            class MyEnum(Enum):
                LHS = "RHS"
            """
        )
        context = compile_root_context(ast_).expand_starred_imports()
        results = FileAnalyser(ast_, context).analyse()

        enum_import = Import(name="Enum", qualified_name="enum.Enum")
        my_enum = Class(name="MyEnum", interface=CallInterface(args=("self", "_id")))
        my_enum_lhs = Name(name="MyEnum.LHS", basename="MyEnum")

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table(
                    [
                        enum_import,
                        my_enum,
                        my_enum_lhs,
                    ],
                    include_root_symbols=True,
                ),
            ),
            file_ir={
                my_enum: {
                    "sets": set(),
                    "gets": {Name("MyEnum.LHS", "MyEnum")},
                    "calls": set(),
                    "dels": set(),
                }
            },
        )

        assert results == expected

    def test_enum_by_module_import(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        ast_ = parse(
            """
            import enum

            class MyEnum(enum.Enum):
                LHS = "RHS"
            """
        )
        context = compile_root_context(ast_).expand_starred_imports()
        results = FileAnalyser(ast_, context).analyse()

        enum_import = Import(name="enum", qualified_name="enum")
        my_enum = Class(name="MyEnum", interface=CallInterface(args=("self", "_id")))
        my_enum_lhs = Name(name="MyEnum.LHS", basename="MyEnum")

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table(
                    [
                        enum_import,
                        my_enum,
                        my_enum_lhs,
                    ],
                    include_root_symbols=True,
                ),
            ),
            file_ir={
                my_enum: {
                    "sets": set(),
                    "gets": {Name("MyEnum.LHS", "MyEnum")},
                    "calls": set(),
                    "dels": set(),
                }
            },
        )

        assert results == expected

    def test_enum_by_starred_import(self, parse: ParseFn):
        ast_ = parse(
            """
            from enum import *

            class MyEnum(Enum):
                LHS = "RHS"
            """
        )
        context = compile_root_context(ast_).expand_starred_imports()
        results = FileAnalyser(ast_, context).analyse()

        my_enum = Class(name="MyEnum", interface=CallInterface(args=("self", "_id")))
        my_enum_lhs = Name(name="MyEnum.LHS", basename="MyEnum")

        expected_context = compile_root_context(ast.parse("from enum import *"))
        expected_context = expected_context.expand_starred_imports()
        expected_context.add(my_enum)
        expected_context.add(my_enum_lhs)

        expected = FileIr(
            context=expected_context,
            file_ir={
                my_enum: {
                    "sets": set(),
                    "gets": {Name("MyEnum.LHS", "MyEnum")},
                    "calls": set(),
                    "dels": set(),
                }
            },
        )

        assert results == expected

    def test_enum_call(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
        constant: str,
    ):
        ast_ = parse(
            """
            from enum import Enum

            class MyEnum(Enum):
                ONE = "one"
                TWO = "two"
                THREE = "three"

            def get_one():
                # actually gets all!
                return MyEnum("one")

            def get_none():
                return 4
            """
        )
        context = compile_root_context(ast_).expand_starred_imports()
        results = FileAnalyser(ast_, context).analyse()

        enum_import = Import(name="Enum", qualified_name="enum.Enum")
        get_one = Func(name="get_one", interface=CallInterface())
        get_none = Func(name="get_none", interface=CallInterface())

        my_enum = Class(name="MyEnum", interface=CallInterface(args=("self", "_id")))
        my_enum_one = Name(name="MyEnum.ONE", basename="MyEnum")
        my_enum_two = Name(name="MyEnum.TWO", basename="MyEnum")
        my_enum_three = Name(name="MyEnum.THREE", basename="MyEnum")
        enum_call = Call(
            name="MyEnum()",
            args=CallArguments(args=("@ReturnValue", constant)),
            target=my_enum,
        )

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table(
                    [
                        enum_import,
                        get_one,
                        get_none,
                        my_enum,
                        my_enum_one,
                        my_enum_two,
                        my_enum_three,
                    ],
                    include_root_symbols=True,
                ),
            ),
            file_ir={
                my_enum: {
                    "sets": set(),
                    "gets": {
                        Name("MyEnum.ONE", "MyEnum"),
                        Name("MyEnum.TWO", "MyEnum"),
                        Name("MyEnum.THREE", "MyEnum"),
                    },
                    "calls": set(),
                    "dels": set(),
                },
                get_one: {
                    "sets": set(),
                    "gets": set(),
                    "calls": {enum_call},
                    "dels": set(),
                },
                get_none: {
                    "sets": set(),
                    "gets": set(),
                    "calls": set(),
                    "dels": set(),
                },
            },
        )

        assert results == expected

    def test_walrus_in_class_static_member(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        ast_ = parse(
            """
            class IAmTheWalrus:
                cls_attr_a = (cls_attr_b := 0)  # Yuck

                def __init__(self):
                    inst_attr_a = (inst_attr_b := 0)  # Just as yuck
            """
        )
        file_analyser = FileAnalyser(ast_, compile_root_context(ast_))
        results = file_analyser.analyse()

        wally = Class(name="IAmTheWalrus", interface=CallInterface(args=("self",)))
        cls_attr_a = Name(name="IAmTheWalrus.cls_attr_a", basename="IAmTheWalrus")
        cls_attr_b = Name(name="IAmTheWalrus.cls_attr_b", basename="IAmTheWalrus")

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table(
                    [
                        wally,
                        cls_attr_a,
                        cls_attr_b,
                    ],
                    include_root_symbols=True,
                ),
            ),
            file_ir={
                wally: {
                    "sets": {
                        Name("inst_attr_a"),
                        Name("inst_attr_b"),
                    },
                    "gets": set(),
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

    def test_walrus_in_class_static_member_in_tuple(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        ast_ = parse(
            """
            class IAmTheWalrus:
                cls_attr_a = (a, cls_attr_b := 0)

                def __init__(self):
                    inst_attr_a = (a, inst_attr_b := 0)
            """
        )
        file_analyser = FileAnalyser(ast_, compile_root_context(ast_))
        results = file_analyser.analyse()

        wally = Class(name="IAmTheWalrus", interface=CallInterface(args=("self",)))
        cls_attr_a = Name(name="IAmTheWalrus.cls_attr_a", basename="IAmTheWalrus")
        cls_attr_b = Name(name="IAmTheWalrus.cls_attr_b", basename="IAmTheWalrus")

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table(
                    [
                        wally,
                        cls_attr_a,
                        cls_attr_b,
                    ],
                    include_root_symbols=True,
                ),
            ),
            file_ir={
                wally: {
                    "sets": {
                        Name("inst_attr_a"),
                        Name("inst_attr_b"),
                    },
                    "gets": {
                        Name("a"),
                    },
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

    def test_walrus_method(
        self,
        parse: ParseFn,
        make_symbol_table: MakeSymbolTableFn,
    ):
        ast_ = parse(
            """
            class IAmTheWalrus:
                def contrived(self):
                    this_is = (a_very_contrived := self.operation)

                @staticmethod
                def more_contrived():
                    if (alias := this_is_just_so_long_i_will_alias_it):
                        return alias
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        wally = Class(name="IAmTheWalrus", interface=AnyCallInterface())
        static = Func(name="IAmTheWalrus.more_contrived", interface=CallInterface())

        expected = FileIr(
            context=Context(
                parent=None,
                symbol_table=make_symbol_table(
                    [
                        wally,
                        static,
                    ],
                    include_root_symbols=True,
                ),
            ),
            file_ir={
                static: {
                    "sets": {
                        Name("alias"),
                    },
                    "gets": {
                        Name("this_is_just_so_long_i_will_alias_it"),
                        Name("alias"),
                    },
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected
