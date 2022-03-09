from rattr.analyser.context import Call, Class, Func, Name, RootContext
from rattr.analyser.file import FileAnalyser


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
        file_analyser = FileAnalyser(_ast, RootContext(_ast))
        file_analyser.analyse()

        assert file_analyser.context.symbol_table == RootSymbolTable(
            Class("Numbers", None, None, None),
            Name("Numbers.One", "Numbers"),
            Name("Numbers.Two", "Numbers"),
            Name("Numbers.Three", "Numbers"),
            Name("Numbers.Four", "Numbers"),
            Name("Numbers.Five", "Numbers"),
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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Class("SomeClass", ["self", "some_arg"], None, None): {
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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        func = Func("func", ["arg"], None, None)
        cls = Class("SomeClass", ["self", "some_arg"], None, None)
        expected = {
            func: {
                "sets": set(),
                "gets": {Name("arg")},
                "dels": set(),
                "calls": {Call("SomeClass()", ["@ReturnValue", "arg"], {}, target=cls)},
            },
            cls: {
                "sets": {
                    Name("self.whatever", "self"),
                    Name("some_arg.good_number", "some_arg"),
                },
                "gets": {
                    Name("some_arg.whatever", "some_arg"),
                },
                "dels": set(),
                "calls": set(),
            },
        }

        # HACK This has to be a repr, can't just compare, idk why
        print(results)
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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        func = Func("func", ["fn_arg"], None, None)
        cls = Class("SomeClass", ["self", "some_arg"], None, None)
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
                "calls": {Call("func()", ["some_arg"], {}, target=func)},
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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        method = Func("SomeClass.method", ["a", "b"], None, None)
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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        cls = Class("SomeClass", ["self", "arg"], None, None)
        method = Func("SomeClass.method", ["a", "b"], None, None)
        expected = {
            cls: {
                "sets": {Name("self.attr", "self")},
                "gets": {Name("arg")},
                "dels": set(),
                "calls": set(),
            },
            method: {
                "sets": {
                    Name("a.attr", "a"),
                },
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
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        method = Func("FibIter.next", [], None, None)
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
        # Explicit import
        _ast = parse(
            """
            from enum import Enum

            class MyEnum(Enum):
                LHS = "RHS"
        """
        )
        _ctx = RootContext(_ast).expand_starred_imports()
        results = FileAnalyser(_ast, _ctx).analyse()

        enum = Class("MyEnum", ["self", "_id"], None, None)
        expected = {
            enum: {
                "sets": set(),
                "gets": {
                    Name("MyEnum.LHS", "MyEnum"),
                },
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
        _ctx = RootContext(_ast).expand_starred_imports()
        results = FileAnalyser(_ast, _ctx).analyse()

        enum = Class("MyEnum", ["self", "_id"], None, None)
        expected = {
            enum: {
                "sets": set(),
                "gets": {
                    Name("MyEnum.LHS", "MyEnum"),
                },
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
        _ctx = RootContext(_ast).expand_starred_imports()
        results = FileAnalyser(_ast, _ctx).analyse()

        enum = Class("MyEnum", ["self", "_id"], None, None)
        expected = {
            enum: {
                "sets": set(),
                "gets": {
                    Name("MyEnum.LHS", "MyEnum"),
                },
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
        _ctx = RootContext(_ast).expand_starred_imports()
        results = FileAnalyser(_ast, _ctx).analyse()

        enum = Class("MyEnum", ["self", "_id"], None, None)
        get_one = Func("get_one", [], None, None)
        get_none = Func("get_none", [], None, None)
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
                "calls": {
                    Call("MyEnum()", ["@ReturnValue", constant("Str")], {}, target=enum)
                },
                "dels": set(),
            },
            get_none: {
                "sets": set(),
                "gets": set(),
                "calls": set(),
                "dels": set(),
            },
        }

        print(results)
        assert results == expected
