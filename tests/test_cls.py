from __future__ import annotations

import pytest

from rattr.analyser.file import FileAnalyser
from rattr.models.context import compile_root_context
from rattr.models.symbol import Call, CallArguments, CallInterface, Class, Func, Name


class TestClassAnalyser:
    def test_class_attributes(self, parse, RootSymbolTable):
        _ast = parse(
            """
            class Numbers(NotARealEnum):
                One = 1
                Two = 2
                Three = 3
                Four, Five = 4, 5
            """
        )
        file_analyser = FileAnalyser(_ast, compile_root_context(_ast))
        file_analyser.analyse()

        assert file_analyser.context.symbol_table == RootSymbolTable(
            Class(name="Numbers", interface=CallInterface()),
            Name(name="Numbers.One", basename="Numbers"),
            Name(name="Numbers.Two", basename="Numbers"),
            Name(name="Numbers.Three", basename="Numbers"),
            Name(name="Numbers.Four", basename="Numbers"),
            Name(name="Numbers.Five", basename="Numbers"),
        )

    def test_class_initialiser(self, parse):
        _ast = parse(
            """
            class SomeClass:
                def __init__(self, some_arg):
                    self.whatever = some_arg.whatever
                    some_arg.good_number = 5    # 5 is a good number
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        some_class_symbol = Class(
            name="SomeClass",
            interface=CallInterface(args=("self", "some_arg")),
        )

        expected = {
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
        }

        assert results == expected

    def test_class_initialiser_integration(self, parse):
        # Func -> __init__
        _ast = parse(
            """
            def func(arg):
                return SomeClass(arg)

            class SomeClass:
                def __init__(self, some_arg):
                    self.whatever = some_arg.whatever
                    some_arg.good_number = 5    # 5 is a good number
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

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

        expected = {
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
        }

        # HACK This has to be a repr, can't just compare, idk why
        assert repr(results._file_ir) == repr(expected)

        # __init__ -> Func
        _ast = parse(
            """
            def func(fn_arg):
                return fn_arg.some_attr

            class SomeClass:
                def __init__(self, some_arg):
                    self.a_thing = func(some_arg)
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

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

        expected = {
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
        }

        assert results == expected

    def test_staticmethod(self, parse):
        # Simple
        _ast = parse(
            """
            class SomeClass:
                @staticmethod
                def method(a, b):
                    a.attr = b.attr
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        method = Func(name="SomeClass.method", interface=CallInterface(args=("a", "b")))

        expected = {
            method: {
                "sets": {
                    Name("a.attr", "a"),
                },
                "gets": {Name("b.attr", "b")},
                "dels": set(),
                "calls": set(),
            }
        }

        assert results == expected

        # Static method in "mixed" class
        _ast = parse(
            """
            class SomeClass:
                def __init__(self, arg):
                    self.attr = arg

                @staticmethod
                def method(a, b):
                    a.attr = b.attr
            """
        )
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        cls = Class(name="SomeClass", interface=CallInterface(args=("self", "arg")))
        method = Func(name="SomeClass.method", interface=CallInterface(args=("a", "b")))

        expected = {
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
        }

        assert results == expected

    def test_class_full(self, parse):
        # Example 1
        _ast = parse(
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
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        method = Func(name="FibIter.next", interface=CallInterface(args=()))

        expected = {
            method: {
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
        }

        assert results == expected

    def test_enum(self, parse):
        enum = Class(name="MyEnum", interface=CallInterface(args=("self", "_id")))

        # Explicit import
        _ast = parse(
            """
            from enum import Enum

            class MyEnum(Enum):
                LHS = "RHS"
            """
        )
        _ctx = compile_root_context(_ast).expand_starred_imports()
        results = FileAnalyser(_ast, _ctx).analyse()

        expected = {
            enum: {
                "sets": set(),
                "gets": {Name("MyEnum.LHS", "MyEnum")},
                "calls": set(),
                "dels": set(),
            }
        }

        assert results == expected

        # Module import
        _ast = parse(
            """
            import enum

            class MyEnum(enum.Enum):
                LHS = "RHS"
            """
        )
        _ctx = compile_root_context(_ast).expand_starred_imports()
        results = FileAnalyser(_ast, _ctx).analyse()

        expected = {
            enum: {
                "sets": set(),
                "gets": {Name("MyEnum.LHS", "MyEnum")},
                "calls": set(),
                "dels": set(),
            }
        }

        assert results == expected

        # Implicit import
        _ast = parse(
            """
            from enum import *

            class MyEnum(Enum):
                LHS = "RHS"
            """
        )
        _ctx = compile_root_context(_ast).expand_starred_imports()
        results = FileAnalyser(_ast, _ctx).analyse()

        expected = {
            enum: {
                "sets": set(),
                "gets": {Name("MyEnum.LHS", "MyEnum")},
                "calls": set(),
                "dels": set(),
            }
        }

        assert results == expected

    def test_enum_call(self, parse, constant):
        _ast = parse(
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
        _ctx = compile_root_context(_ast).expand_starred_imports()
        results = FileAnalyser(_ast, _ctx).analyse()

        enum = Class(name="MyEnum", interface=CallInterface(args=("self", "_id")))
        enum_call = Call(
            name="MyEnum()",
            args=CallArguments(args=("@ReturnValue", constant("Str"))),
            target=enum,
        )
        get_one = Func(name="get_one", interface=CallInterface())
        get_none = Func(name="get_none", interface=CallInterface())

        expected = {
            enum: {
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
        }

        assert results == expected

    @pytest.mark.py_3_8_plus()
    def test_walrus(self, parse, RootSymbolTable):
        wally = Class(name="IAmTheWalrus", interface=CallInterface(args=("self",)))
        cls_attr_a = Name(name="IAmTheWalrus.cls_attr_a", basename="IAmTheWalrus")
        cls_attr_b = Name(name="IAmTheWalrus.cls_attr_b", basename="IAmTheWalrus")

        # "Normal"
        _ast = parse(
            """
            class IAmTheWalrus:
                cls_attr_a = (cls_attr_b := 0)  # Yuck

                def __init__(self):
                    inst_attr_a = (inst_attr_b := 0)  # Just as yuck
            """
        )
        file_analyser = FileAnalyser(_ast, compile_root_context(_ast))
        results = file_analyser.analyse()

        assert file_analyser.context.symbol_table == RootSymbolTable(
            wally, cls_attr_a, cls_attr_b
        )

        expected = {
            wally: {
                "sets": {
                    Name("inst_attr_a"),
                    Name("inst_attr_b"),
                },
                "gets": set(),
                "dels": set(),
                "calls": set(),
            }
        }
        assert results == expected

        # Tuple'd
        _ast = parse(
            """
            class IAmTheWalrus:
                cls_attr_a = (a, cls_attr_b := 0)

                def __init__(self):
                    inst_attr_a = (a, inst_attr_b := 0)
            """
        )
        file_analyser = FileAnalyser(_ast, compile_root_context(_ast))
        results = file_analyser.analyse()

        assert file_analyser.context.symbol_table == RootSymbolTable(
            wally, cls_attr_a, cls_attr_b
        )

        expected = {
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
        }
        assert results == expected

    @pytest.mark.py_3_8_plus()
    def test_walrus_method(self, parse):
        _ast = parse(
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
        results = FileAnalyser(_ast, compile_root_context(_ast)).analyse()

        static = Func(name="IAmTheWalrus.more_contrived", interface=CallInterface())

        expected = {
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
        }

        assert results == expected
