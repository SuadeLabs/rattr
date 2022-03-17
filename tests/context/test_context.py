import ast
from unittest import mock

from rattr.analyser.context import (
    Builtin,
    Class,
    Context,
    Func,
    Import,
    Name,
    RootContext,
    SymbolTable,
)


class TestContext:
    def test_add(self):
        # Test add
        root = Context(None)
        root.add(Name("var_one"))

        child = Context(root)
        child.add(Name("var_two"))

        assert "var_one" in root
        assert "var_one" in child

        assert "var_two" not in root
        assert "var_two" in child

        # Test add argument
        root = Context(None)
        root.add(Name("x"))

        fn_ctx = Context(root)
        fn_ctx.add(Name("x"), is_argument=True)

        assert root.symbol_table == SymbolTable(**{"x": Name("x")})
        assert fn_ctx.symbol_table == SymbolTable(**{"x": Name("x")})

    def test_add_all(self):
        root = Context(None)
        root.add_all([Name("a"), Name("b")])

        assert root.symbol_table == SymbolTable(
            **{
                "a": Name("a"),
                "b": Name("b"),
            }
        )

    def test_remove(self):
        # Remove from self
        root = Context(None)
        root.add_all([Name("a"), Name("b")])
        assert root.symbol_table == SymbolTable(
            **{
                "a": Name("a"),
                "b": Name("b"),
            }
        )

        root.remove("a")
        assert root.symbol_table == SymbolTable(**{"b": Name("b")})

        # Remove from parent
        root = Context(None)
        root.add_all([Name("a"), Name("b")])
        child = Context(root)

        assert root.symbol_table == SymbolTable(
            **{
                "a": Name("a"),
                "b": Name("b"),
            }
        )
        assert child.symbol_table == SymbolTable()

        child.remove("a")
        assert root.symbol_table == SymbolTable(**{"b": Name("b")})
        assert child.symbol_table == SymbolTable()

        # Remove non-existent
        root = Context(None)
        root.add_all([Name("a"), Name("b")])
        child = Context(root)

        root.remove("fake")
        child.remove("false")

        assert root.symbol_table == SymbolTable(
            **{
                "a": Name("a"),
                "b": Name("b"),
            }
        )
        assert child.symbol_table == SymbolTable()

    def test_remove_all(self):
        # Remove from self
        root = Context(None)
        root.add_all([Name("a"), Name("b")])
        assert root.symbol_table == SymbolTable(
            **{
                "a": Name("a"),
                "b": Name("b"),
            }
        )

        root.remove_all(list(root.symbol_table.names()))
        assert root.symbol_table == SymbolTable()

        # Mixed removal
        root = Context(None)
        root.add(Name("a"))
        child = Context(root)
        child.add(Name("b"))

        assert root.symbol_table == SymbolTable(**{"a": Name("a")})
        assert child.symbol_table == SymbolTable(**{"b": Name("b")})

        child.remove_all(["a", "b", "c"])

        assert root.symbol_table == SymbolTable()
        assert child.symbol_table == SymbolTable()

    def test_get(self):
        root = Context(None)
        root.add_all([Name("a"), Name("b")])

        assert root.get("a") == Name("a")
        assert root.get("b") == Name("b")
        assert root.get("x") is None

    def test_get_call_target(self, capfd, config):
        # No target
        root = Context(None)
        assert root.get_call_target("anything()", None) is None

        output, _ = capfd.readouterr()
        assert "unable to resolve call" in output

        # Target is not "Callable"
        root = Context(None)
        root.add(Name("a"))
        child = Context(root)

        assert child.get_call_target("a()", None) == Name("a")

        output, _ = capfd.readouterr()
        assert "is not callable" in output

        # Target is not "Callable" -- higher-order function
        root = Context(None)
        root.add(Name("a"))
        child = Context(root)

        root.get_call_target("a()", None)

        output, _ = capfd.readouterr()
        assert "likely a procedural parameter" in output

        # Target is not "Callable" -- higher-order function
        root = Context(None)
        root.add(Name("a"))
        child = Context(root)

        with config("show_low_priority_warnings", True):
            root.get_call_target("a.method()", None)

        output, _ = capfd.readouterr()
        assert "unable to resolve call to method" in output

        # Found target
        root = Context(None)
        a_symbol = Func("a", [], None, None)
        root.add(a_symbol)

        assert root.get_call_target("a()", None) == a_symbol

    def test_declares(self):
        root = Context(None)
        root.add(Name("a"))
        child = Context(root)
        child.add(Name("b"))

        assert root.declares("a")
        assert not root.declares("b")

        assert not child.declares("a")
        assert child.declares("b")

    def test_in(self):
        root = Context(None)
        root.add(Name("a"))
        child = Context(root)
        child.add(Name("b"))

        assert "a" in root
        assert "b" not in root

        assert "a" in child
        assert "b" in child

    def test_add_identifiers_to_context(self):
        # Single identifier
        expr = ast.parse("a = 1").body[0].targets[0]  # = a

        root = Context(None)

        assert root.symbol_table == SymbolTable()
        root.add_identifiers_to_context(expr)
        assert root.symbol_table == SymbolTable(**{"a": Name("a")})

        # Multiple identifiers per call (i.e. tuple assignment)
        expr = ast.parse("a, b, c = 1, 2, 3").body[0].targets[0]  # = (a, b, c)

        root = Context(None)

        assert root.symbol_table == SymbolTable()
        root.add_identifiers_to_context(expr)
        assert root.symbol_table == SymbolTable(
            **{
                "a": Name("a"),
                "b": Name("b"),
                "c": Name("c"),
            }
        )

    def test_del_identifiers_from_context(self):
        # Single identifier
        expr = ast.parse("del a").body[0].targets[0]  # = a

        root = Context(None)
        root.add(Name("a"))

        assert root.symbol_table == SymbolTable(**{"a": Name("a")})
        root.del_identifiers_from_context(expr)
        assert root.symbol_table == SymbolTable()

        # Multiple identifiers
        # `del, x, y, ...z` produces list of `ast.Name`s not a tuple
        expr_a = ast.parse("del a, b").body[0].targets[0]  # = a
        expr_b = ast.parse("del a, b").body[0].targets[1]  # = b

        root = Context(None)
        root.add(Name("a"))
        root.add(Name("b"))

        assert root.symbol_table == SymbolTable(
            **{
                "a": Name("a"),
                "b": Name("b"),
            }
        )
        root.del_identifiers_from_context(expr_a)
        root.del_identifiers_from_context(expr_b)
        assert root.symbol_table == SymbolTable()

    def test_push_arguments_to_context(self, parse):
        # No args
        arguments = (
            parse(
                """
            def fn():
                pass
        """
            )
            .body[0]
            .args
        )

        root = Context(None)

        assert root.symbol_table == SymbolTable()
        root.push_arguments_to_context(arguments)
        assert root.symbol_table == SymbolTable()

        # Many args
        arguments = (
            parse(
                """
            def fn(a, b, c=1, d=2, *x, **y):
                pass
        """
            )
            .body[0]
            .args
        )

        root = Context(None)

        assert root.symbol_table == SymbolTable()
        root.push_arguments_to_context(arguments)
        assert root.symbol_table == SymbolTable(
            **{
                "a": Name("a"),
                "b": Name("b"),
                "c": Name("c"),
                "d": Name("d"),
                "x": Name("x"),
                "y": Name("y"),
            }
        )

    def test_redefinition_in_scope(self):
        root = Context(None)
        root.add(Name("var_one"))
        root.add(Name("var_one"))

        assert root.symbol_table == SymbolTable(**{"var_one": Name("var_one")})

    def test_redefinition_in_child_scope(self):
        root = Context(None)
        root.add(Name("var_one"))

        child = Context(root)
        child.add(Name("var_one"))

        assert root.symbol_table == SymbolTable(**{"var_one": Name("var_one")})
        assert child.symbol_table == SymbolTable()

    def test_is_import(self):
        root = Context(None)
        root.add(Import("math", "math"))
        root.add(Import("np", "numpy"))
        root.add(Import("join", "os.path.join"))

        child = Context(root)

        # From within root
        assert root.is_import("math")
        assert root.is_import("np")
        assert root.is_import("join")
        assert not root.is_import("numpy")
        assert not root.is_import("os")
        assert not root.is_import("os.path")
        assert not root.is_import("os.path.join")

        # From within child
        assert child.is_import("math")
        assert child.is_import("np")
        assert child.is_import("join")
        assert not child.is_import("numpy")
        assert not child.is_import("os")
        assert not child.is_import("os.path")
        assert not child.is_import("os.path.join")


class TestRootContext_ContextFromPython:
    def test_module_level_attributes(self, parse):
        _ast = parse(
            """
            # A blank context
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None

        module_level_attributes = [
            "__annotations__",
            "__builtins__",
            "__cached__",
            "__doc__",
            "__file__",
            "__loader__",
            "__name__",
            "__package__",
            "__spec__",
        ]

        for attr in module_level_attributes:
            assert attr in _ctx.symbol_table

    def test_builtins(self, parse):
        _ast = parse(
            """
            # A blank context
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None

        # Some selected examples
        assert "print" in _ctx.symbol_table
        assert "max" in _ctx.symbol_table
        assert "len" in _ctx.symbol_table

        assert "Exception" in _ctx.symbol_table
        assert "KeyError" in _ctx.symbol_table
        assert "TypeError" in _ctx.symbol_table

    def test_affective_builtins(self, parse):
        _ast = parse(
            """
            # A blank context
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None

        assert _ctx.symbol_table.get("does_not_exist") is None
        assert _ctx.symbol_table.get("print") == Builtin("print", has_affect=False)
        assert _ctx.symbol_table.get("setattr") == Builtin("setattr", has_affect=True)


class TestRootContext_Imports:
    def test_import(self, parse, RootSymbolTable):
        _ast = parse(
            """
            import math
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Import("math", "math"),
        )

    def test_import_as(self, parse, RootSymbolTable):
        _ast = parse(
            """
            import math as m
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Import("m", "math"),
        )

    def test_import_list(self, parse, RootSymbolTable, capfd, config):
        _ast = parse(
            """
            import os, math
        """
        )
        with config("show_low_priority_warnings", True):
            _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Import("os"),
            Import("math"),
        )

        output, _ = capfd.readouterr()
        assert "info" in output

    def test_from_import(self, parse, RootSymbolTable):
        _ast = parse(
            """
            from os.path import isfile
            from math import sin, cos
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Import("isfile", "os.path.isfile"),
            Import("sin", "math.sin"),
            Import("cos", "math.cos"),
        )

    def test_from_import_as(self, parse, RootSymbolTable):
        _ast = parse(
            """
            from os import path as path_utils
            from math import power as exp, some_func
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Import("path_utils", "os.path"),
            Import("exp", "math.power"),
            Import("some_func", "math.some_func"),
        )

    def test_from_import_star(self, parse, RootSymbolTable, capfd):
        _ast = parse(
            """
            from math import *
        """
        )

        _ctx = RootContext(_ast)

        # Were error.fatal not to be called,
        # assert that it would have been correct
        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(Import("*", "math"))

        output, _ = capfd.readouterr()
        assert "warning" in output and "*" in output

    def test_nested_from_import(self, parse, RootSymbolTable):
        _ast = parse(
            """
            from os.path import join
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(Import("join", "os.path.join"))

    def test_multiple_starred_imports(self, parse, RootSymbolTable):
        _ast = parse(
            """
            from os import *
            from math import *
        """
        )

        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert Import("*", "os") in _ctx.symbol_table.symbols()
        assert Import("*", "math") in _ctx.symbol_table.symbols()

    def test_import_in_child_context(self, parse, RootSymbolTable):
        # In if, try, for, etc
        _ast = parse(
            """
            if something:
                from math import *
        """
        )

        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Import("*", "math"),
        )

        # In function, class, etc
        _ast = parse(
            """
            def fn():
                from math import *
        """
        )

        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Func("fn", [], None, None),
        )
        assert Import("*", "math") not in _ctx.symbol_table.symbols()


class TestRootContext_Assigns:
    def test_assignment(self, parse, RootSymbolTable):
        _ast = parse(
            """
            a = 42
            a = "reassigned!"

            b = hhgttg()

            x, y, = 1, 2
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Name("a"),
            Name("b"),
            Name("x"),
            Name("y"),
        )

    def test_ann_assignment(self, parse, RootSymbolTable):
        _ast = parse(
            """
            a: int = 42
            b: str = "an string!"
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Name("a"),
            Name("b"),
        )

    def test_aug_assignment(self, parse, RootSymbolTable):
        _ast = parse(
            """
            a = 7
            a += 5

            b %= "fmt"
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Name("a"),
            Name("b"),
        )


class TestRootContext_FunctionDefs:
    def test_function_def(self, parse, RootSymbolTable):
        _ast = parse(
            """
            def fn_one(a, b):
                pass

            def fn_two(c):
                var = "i shouldn't be in the root context!"
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Func("fn_one", ["a", "b"], None, None),
            Func("fn_two", ["c"], None, None),
        )

    def test_async_function_def(self, parse, RootSymbolTable):
        _ast = parse(
            """
            async def fn_one(a, b):
                pass

            async def fn_two(c):
                var = "i shouldn't be in the root context!"
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Func("fn_one", ["a", "b"], None, None, is_async=True),
            Func("fn_two", ["c"], None, None, is_async=True),
        )

    def test_lambda_anonymous(self, parse, RootSymbolTable, capfd):
        _ast = parse(
            """
            lambda: 1
        """
        )

        with mock.patch("sys.exit") as _exit:
            RootContext(_ast)

        output, _ = capfd.readouterr()
        assert "top-level lambdas must be named" in output
        assert _exit.called

    def test_lambda_named(self, parse, RootSymbolTable, capfd):
        # Normal
        _ast = parse(
            """
            x = lambda a, b: 1
            y: type = lambda: 1
            z = lambda *args: 1
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Func("x", ["a", "b"], None, None),
            Func("y", [], None, None),
            Func("z", [], "args", None),
        )

        # Bad: Multiple LHS and RHS
        _ast = parse(
            """
            x, y = lambda a, b: 1, 2
        """
        )

        with mock.patch("sys.exit") as _exit:
            RootContext(_ast)

        output, _ = capfd.readouterr()
        assert "lambda assignment must be one-to-one" in output
        assert _exit.called

        # Bad: Multiple LHS
        _ast = parse(
            """
            x, y = lambda a: 1
        """
        )

        with mock.patch("sys.exit") as _exit:
            RootContext(_ast)

        output, _ = capfd.readouterr()
        assert "lambda assignment must be one-to-one" in output
        assert _exit.called

        # Bad: Multiple RHS
        _ast = parse(
            """
            x = lambda a, b: 1, 2
        """
        )

        with mock.patch("sys.exit") as _exit:
            RootContext(_ast)

        output, _ = capfd.readouterr()
        assert "lambda assignment must be one-to-one" in output
        assert _exit.called


class TestRootContext_If:
    def test_if(self, parse, RootSymbolTable):
        _ast = parse(
            """
            if some_variable == "some value":
                def fn(a):
                    pass

                global_var = 40
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Func("fn", ["a"], None, None),
            Name("global_var"),
        )

    def test_nested_if(self, parse, RootSymbolTable):
        _ast = parse(
            """
            if some_variable == "some value":
                if some_other_variable == "some other value":
                    def fn(a):
                        pass

                    global_var = 40
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Func("fn", ["a"], None, None),
            Name("global_var"),
        )


class TestRootContext_For:
    def test_for(self, parse, RootSymbolTable):
        _ast = parse(
            """
            for i in ITER:
                def fn(a):
                    pass

                global_var = 40
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Func("fn", ["a"], None, None),
            Name("global_var"),
        )

    def test_nested_for(self, parse, RootSymbolTable):
        _ast = parse(
            """
            for iter in ITER_OF_ITERS:
                for i in iter:
                    def fn(a):
                        pass

                    global_var = 40
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Func("fn", ["a"], None, None),
            Name("global_var"),
        )

    def test_async_for(self, parse, RootSymbolTable):
        _ast = parse(
            """
            async for i in ITER:
                def fn(a):
                    pass

                global_var = 40
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Func("fn", ["a"], None, None),
            Name("global_var"),
        )


class TestRootContext_While:
    def test_while(self, parse, RootSymbolTable):
        _ast = parse(
            """
            while True:
                def fn(a):
                    pass

                global_var = 40
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Func("fn", ["a"], None, None),
            Name("global_var"),
        )

    def test_nested_while(self, parse, RootSymbolTable):
        _ast = parse(
            """
            while True:
                while True:
                    def fn(a):
                        pass

                    global_var = 40
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Func("fn", ["a"], None, None),
            Name("global_var"),
        )


class TestRootContext_Try:
    def test_try(self, parse, RootSymbolTable):
        _ast = parse(
            """
            try:
                global_a = 1
            except TypeError:
                global_b = 2
            except:
                global_c = 3
            else:
                global_d = 4
            finally:
                global_e = 5
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Name("global_a"),
            Name("global_b"),
            Name("global_c"),
            Name("global_d"),
            Name("global_e"),
        )

    def test_nested_try(self, parse, RootSymbolTable):
        _ast = parse(
            """
            try:
                try:
                    global_a = 1
                except TypeError:
                    global_b = 2
                except:
                    global_c = 3
                else:
                    global_d = 4
                finally:
                    global_e = 5
            finally:
                global_z = 26
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Name("global_a"),
            Name("global_b"),
            Name("global_c"),
            Name("global_d"),
            Name("global_e"),
            Name("global_z"),
        )


class TestRootContext_With:
    def test_with(self, parse, RootSymbolTable):
        _ast = parse(
            """
            with context_manager() as ctx:
                def fn(a):
                    pass

                global_var = 40
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Func("fn", ["a"], None, None),
            Name("global_var"),
        )

    def test_nested_with(self, parse, RootSymbolTable):
        _ast = parse(
            """
            with context_manager() as ctx:
                with ctx() as inner_ctx:
                    def fn(a):
                        pass

                    global_var = 40
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Func("fn", ["a"], None, None),
            Name("global_var"),
        )

    def test_async_with(self, parse, RootSymbolTable):
        _ast = parse(
            """
            async with context_manager() as ctx:
                def fn(a):
                    pass

                global_var = 40
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Func("fn", ["a"], None, None),
            Name("global_var"),
        )


class TestRootContext_ClassDefs:
    def test_class_def(self, parse, RootSymbolTable):
        _ast = parse(
            """
            class TopLevel:
                def __init__(self, a):
                    self.a = a

                def method(self):
                    var = "i shouldn't be in the root context!"
                    return var + " see, i'm not!"
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Class("TopLevel", None, None, None),
        )


class TestRootContext_Ignored:
    def test_class_def(self, parse, RootSymbolTable, capfd):
        _ast = parse(
            """
            '''
            Docstring at module level.
            '''
        """
        )
        _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable()

        output, _ = capfd.readouterr()
        assert output == ""


class TestRootContext:

    # Longer "end-to-end" style test -- i.e. context over a whole module

    def test_module(self, parse, RootSymbolTable, capfd):
        _ast = parse(
            """
            import a_module

            from another_module import some_function

            def my_function(a, b):
                sum = a + b
                return sum * sum

            class MyClass:
                def __init__(self):
                    self.data = list()

                def get_data(self):
                    return self.data
        """
        )

        with mock.patch("sys.exit") as _exit:
            _ctx = RootContext(_ast)

        assert _ctx.parent is None
        assert _ctx.symbol_table == RootSymbolTable(
            Import("a_module", "a_module"),
            Import("some_function", "another_module.some_function"),
            Func("my_function", ["a", "b"], None, None),
            Class("MyClass", None, None, None),
        )

        # NOTE `a_module` and `another_module` don't exist
        assert _exit.call_count == 2

        output, _ = capfd.readouterr()
        assert "unable to find module 'a_module'" in output
        assert "unable to find module 'another_module'" in output
