from rattr.analyser.context import (
    Builtin,
    Call,
    Class,
    Func,
    Name,
    RootContext,
)
from rattr.analyser.file import FileAnalyser


class TestFunctionAnalyser:
    def test_basic_function(self, parse):
        _ast = parse(
            """
            def a_func(arg):
                arg.sets_me = "value"
                return arg.gets_me
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "calls": set(),
                "dels": set(),
                "gets": {Name("arg.gets_me", "arg")},
                "sets": {Name("arg.sets_me", "arg")},
            }
        }

        assert results == expected

    def test_multiple_functions(self, parse):
        _ast = parse(
            """
            def a_func(arg):
                arg.sets_me = "value"
                return arg.gets_me

            def another_func(arg):
                arg.attr = "this function only sets"
                arg.attr_two = "see!"
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "calls": set(),
                "dels": set(),
                "gets": {Name("arg.gets_me", "arg")},
                "sets": {Name("arg.sets_me", "arg")},
            },
            Func("another_func", ["arg"], None, None): {
                "calls": set(),
                "dels": set(),
                "gets": set(),
                "sets": {
                    Name("arg.attr", "arg"),
                    Name("arg.attr_two", "arg"),
                },
            },
        }

        assert results == expected

    def test_conditional(self, parse):
        _ast = parse(
            """
            def a_func(arg):
                if debug:
                    return False
                return arg.attr == "target value"
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("debug"),
                    Name("arg.attr", "arg"),
                },
                "sets": set(),
            },
        }

        assert results == expected

    def test_nested_conditional(self, parse):
        _ast = parse(
            """
            def a_func(arg):
                if c1:
                    if c2:
                        return arg.foo
                return arg.bar
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("c1"),
                    Name("c2"),
                    Name("arg.foo", "arg"),
                    Name("arg.bar", "arg"),
                },
                "sets": set(),
            },
        }

        assert results == expected

    def test_nested_function(self, parse):
        # NOTE Does not test function following, `arg` always named such
        _ast = parse(
            """
            def a_func(arg):
                def inner(arg):
                    return arg.foo
                return inner(arg)
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        inner_symbol = Func("inner", ["arg"], None, None)
        expected = {
            Func("a_func", ["arg"], None, None): {
                "calls": {
                    Call("inner()", ["arg"], {}, inner_symbol),
                },
                "dels": set(),
                "gets": {
                    Name("arg"),
                    Name("arg.foo", "arg"),
                },
                "sets": set(),
            },
        }

        assert results == expected

    # def test_comprehensions(self, parse):
    #     _ast = parse("""
    #         def list_comp(arg):
    #             return [a.prop for a in arg.iter]
    #     """)
    #     results = FileAnalyser(_ast, RootContext(_ast)).analyse()

    #     expected = {
    #         Func("list_comp", ["arg"], None, None): {
    #             "calls": set(),
    #             "dels": set(),
    #             "gets": {
    #                 # ...
    #             },
    #             "sets": set()
    #         },
    #     }

    #     assert results == expected

    def test_getattr(self, parse):
        # Simple
        _ast = parse(
            """
            def a_func(arg):
                return getattr(arg, "attr")
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

        # Nested
        _ast = parse(
            """
            def a_func(arg):
                return getattr(getattr(arg, "inner"), "outer")
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("arg.inner.outer", "arg"),
                },
                "sets": set(),
            },
        }

        assert results == expected

        # Nested
        _ast = parse(
            """
            def a_func(arg):
                return getattr(getattr(arg.b[0], "inner"), "outer")
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("arg.b[].inner.outer", "arg"),
                },
                "sets": set(),
            },
        }

        assert results == expected

    def test_hasattr(self, parse):
        # Simple
        _ast = parse(
            """
            def a_func(arg):
                return hasattr(arg, "attr")
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

        # Nested
        _ast = parse(
            """
            def a_func(arg):
                return hasattr(hasattr(arg, "inner"), "outer")
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("arg.inner.outer", "arg"),
                },
                "sets": set(),
            },
        }

        assert results == expected

        # Complex
        _ast = parse(
            """
            def a_func(arg):
                return hasattr(hasattr(arg.b[0], "inner"), "outer")
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "calls": set(),
                "dels": set(),
                "gets": {
                    Name("arg.b[].inner.outer", "arg"),
                },
                "sets": set(),
            },
        }

        assert results == expected

    def test_setattr(self, parse):
        # Simple
        _ast = parse(
            """
            def a_func(arg):
                setattr(arg, "attr", "value")
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "calls": set(),
                "dels": set(),
                "gets": set(),
                "sets": {
                    Name("arg.attr", "arg"),
                },
            },
        }

        assert results == expected

        # Complex
        _ast = parse(
            """
            def a_func(arg):
                return setattr(arg.b[0], "attr", "value")
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "calls": set(),
                "dels": set(),
                "gets": set(),
                "sets": {
                    Name("arg.b[].attr", "arg"),
                },
            },
        }

        assert results == expected

    def test_delattr(self, parse):
        # Simple
        _ast = parse(
            """
            def a_func(arg):
                delattr(arg, "attr")
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "gets": set(),
                "sets": set(),
                "dels": {
                    Name("arg.attr", "arg"),
                },
                "calls": set(),
            },
        }

        assert results == expected

        # Complex
        _ast = parse(
            """
            def a_func(arg):
                return delattr(arg.b[0], "attr")
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "gets": set(),
                "sets": set(),
                "dels": {
                    Name("arg.b[].attr", "arg"),
                },
                "calls": set(),
            },
        }

        assert results == expected

    def test_format(self, parse, constant):
        as_func = Builtin("format", has_affect=False)

        # Simple
        _ast = parse(
            """
            def a_func(arg):
                return format(arg, "b")
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "calls": {
                    Call("format()", ["arg", constant("Str")], {}, target=as_func)
                },
                "dels": set(),
                "gets": {Name("arg")},
                "sets": set(),
            },
        }

        assert results == expected

        # Complex
        _ast = parse(
            """
            def a_func(arg):
                return format(getattr(arg, "attr"), "b")
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "calls": {
                    Call("format()", ["arg.attr", constant("Str")], {}, target=as_func)
                },
                "dels": set(),
                "gets": {
                    Name("arg.attr", "arg"),
                },
                "sets": set(),
            },
        }

        assert results == expected

    def test_lambda(self, parse, capfd):
        # The Good
        _ast = parse(
            """
            global_lamb = lambda x: x.attr

            def func_one(arg):
                return global_lamb(arg)

            def func_two(arg):
                return map(lambda x: x*x, [1, 2, 3])
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        global_lamb = Func("global_lamb", ["x"], None, None)
        func_one = Func("func_one", ["arg"], None, None)
        func_two = Func("func_two", ["arg"], None, None)
        _map = Builtin("map", has_affect=False)
        expected = {
            global_lamb: {
                "gets": {
                    Name("x.attr", "x"),
                },
                "sets": set(),
                "dels": set(),
                "calls": set(),
            },
            func_one: {
                "gets": {Name("arg")},
                "sets": set(),
                "dels": set(),
                "calls": {Call("global_lamb()", ["arg"], {}, target=global_lamb)},
            },
            func_two: {
                "gets": {
                    Name("x"),
                },
                "sets": set(),
                "dels": set(),
                "calls": {
                    Call("map()", ["@Lambda", "@List"], {}, target=_map),
                },
            },
        }

        assert results == expected

    def test_class_init(self, parse, capfd):
        _ast = parse(
            """
            class ClassName:
                def __init__(self, arg):
                    self.attr = arg

            def a_func(blarg):
                thing = ClassName(blarg)
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        cls = Class("ClassName", ["self", "arg"], None, None)
        a_func = Func("a_func", ["blarg"], None, None)
        expected = {
            cls: {
                "sets": {
                    Name("self.attr", "self"),
                },
                "gets": {Name("arg")},
                "dels": set(),
                "calls": set(),
            },
            a_func: {
                "sets": {Name("thing")},
                "gets": {Name("blarg")},
                "dels": set(),
                "calls": {Call("ClassName()", ["thing", "blarg"], {}, target=cls)},
            },
        }

        assert results == expected

    def test_return_value(self, parse, constant):
        # No return value
        _ast = parse(
            """
            def a_func(blarg):
                return
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        a_func = Func("a_func", ["blarg"], None, None)
        expected = {
            a_func: {
                "sets": set(),
                "gets": set(),
                "dels": set(),
                "calls": set(),
            },
        }

        assert results == expected

        # Literal
        _ast = parse(
            """
            def a_func(blarg):
                return 4
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        a_func = Func("a_func", ["blarg"], None, None)
        expected = {
            a_func: {
                "sets": set(),
                "gets": set(),
                "dels": set(),
                "calls": set(),
            },
        }

        assert results == expected

        # Local var
        _ast = parse(
            """
            def a_func(blarg):
                return blarg.attr
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        a_func = Func("a_func", ["blarg"], None, None)
        expected = {
            a_func: {
                "sets": set(),
                "gets": {
                    Name("blarg.attr", "blarg"),
                },
                "dels": set(),
                "calls": set(),
            },
        }

        assert results == expected

        # Tuple (w/o class)
        _ast = parse(
            """
            def a_func(blarg):
                return blarg.attr, 1, a_call(blarg.another_attr)
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        a_func = Func("a_func", ["blarg"], None, None)
        expected = {
            a_func: {
                "sets": set(),
                "gets": {
                    Name("blarg.attr", "blarg"),
                    Name("blarg.another_attr", "blarg"),
                },
                "dels": set(),
                "calls": {Call("a_call()", ["blarg.another_attr"], {}, target=None)},
            },
        }

        assert results == expected

        # Class
        _ast = parse(
            """
            class MyEnum(Enum):
                first = "one"
                second = "two"

            def a_func(blarg):
                return MyEnum("one")
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        a_func = Func("a_func", ["blarg"], None, None)
        MyEnum = Class("MyEnum", ["self", "_id"], None, None)
        expected = {
            a_func: {
                "sets": set(),
                "gets": set(),
                "dels": set(),
                "calls": {
                    Call(
                        "MyEnum()", ["@ReturnValue", constant("Str")], {}, target=MyEnum
                    ),
                },
            },
            MyEnum: {
                "sets": set(),
                "gets": {
                    Name("MyEnum.first", "MyEnum"),
                    Name("MyEnum.second", "MyEnum"),
                },
                "calls": set(),
                "dels": set(),
            },
        }

        assert results == expected

        # Tuple (w/ class)
        _ast = parse(
            """
            class MyEnum(Enum):
                first = "one"
                second = "two"

            def a_func(blarg):
                return 1, MyEnum("one"), blarg.attr
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        a_func = Func("a_func", ["blarg"], None, None)
        MyEnum = Class("MyEnum", ["self", "_id"], None, None)
        expected = {
            a_func: {
                "sets": set(),
                "gets": {
                    Name("blarg.attr", "blarg"),
                },
                "dels": set(),
                "calls": {
                    Call(
                        "MyEnum()", ["@ReturnValue", constant("Str")], {}, target=MyEnum
                    ),
                },
            },
            MyEnum: {
                "sets": set(),
                "gets": {
                    Name("MyEnum.first", "MyEnum"),
                    Name("MyEnum.second", "MyEnum"),
                },
                "calls": set(),
                "dels": set(),
            },
        }

        print(results)
        assert results == expected
