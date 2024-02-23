from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from rattr.models.context import Context, compile_root_context
from rattr.models.context._root_context import MODULE_LEVEL_DUNDER_ATTRS
from rattr.models.symbol import CallInterface, Class, Func, Import, Name
from tests.shared import compare_symbol_table_symbols, match_output

if TYPE_CHECKING:
    from rattr.models.symbol import Builtin
    from tests.shared import ArgumentsFn, MakeSymbolTableFn, ParseFn


@pytest.fixture
def root_context() -> Context:
    return compile_root_context(ast.Module(body=[]))


def test_root_context_includes_module_level_attributes(root_context: Context):
    for attr in MODULE_LEVEL_DUNDER_ATTRS:
        assert attr in root_context.symbol_table.names


def test_root_context_includes_python_builtins(root_context: Context):
    example_builtins = (
        # functions
        "print",
        "max",
        "len",
        # classes / errors
        "Exception",
        "KeyError",
        "TypeError",
    )

    for attr in example_builtins:
        assert attr in root_context.symbol_table.names


def test_root_context_python_builtins_have_correct_affect_status(root_context: Context):
    print_symbol: Builtin = root_context.get("print")
    setattr_symbol: Builtin = root_context.get("setattr")

    assert not print_symbol.has_affect
    assert setattr_symbol.has_affect


def test_root_context_import(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        import math
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Import(name="math", qualified_name="math", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_import_as(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        import math as m
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Import(name="m", qualified_name="math", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_import_list(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
    arguments: ArgumentsFn,
    capfd: pytest.CaptureFixture[str],
):
    module_ast = parse(
        """
        import os, math
        """
    )

    with arguments(_warning_level="all"):
        context = compile_root_context(module_ast)

    expected = make_symbol_table(
        [
            Import(name="os", qualified_name="os", location=mock.ANY),
            Import(name="math", qualified_name="math", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)

    _, stderr = capfd.readouterr()
    assert match_output(stderr, ["do not import multiple modules on one line"])


def test_root_context_import_from(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        from os.path import isfile
        from math import sin, cos
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Import(name="isfile", qualified_name="os.path.isfile", location=mock.ANY),
            Import(name="sin", qualified_name="math.sin", location=mock.ANY),
            Import(name="cos", qualified_name="math.cos", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_import_from_as(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        from os import path as path_utils
        from math import power as exp, cos
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Import(name="path_utils", qualified_name="os.path", location=mock.ANY),
            Import(name="exp", qualified_name="math.power", location=mock.ANY),
            Import(name="cos", qualified_name="math.cos", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_import_from_star(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
    capfd: pytest.CaptureFixture[str],
):
    module_ast = parse(
        """
        from math import *
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Import(name="*", qualified_name="math", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)

    _, stderr = capfd.readouterr()
    assert match_output(
        stderr,
        ["do not use 'from math import *' outside of __init__.py files, be explicit"],
    )


def test_root_context_import_from_submodule(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        from os.path import join
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Import(name="join", qualified_name="os.path.join", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_import_multiple_starred(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        from os import *
        from math import *
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Import(name="*", qualified_name="os", location=mock.ANY),
            Import(name="*", qualified_name="math", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_import_inside_stmt_block(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        if something:
            from math import *
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Import(name="*", qualified_name="math", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_import_inside_function_block(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        def fn():
            from math import *
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Func(name="fn", location=mock.ANY, interface=CallInterface()),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_assignment(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        a = 42
        a = "reassigned!"

        b = hhgttg()

        x, y, = 1, 2
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Name("a", location=mock.ANY),
            Name("b", location=mock.ANY),
            Name("x", location=mock.ANY),
            Name("y", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_ann_assignment(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        a: int = 42
        b: str = "an string!"
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Name("a", location=mock.ANY),
            Name("b", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_aug_assignment(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        a = 7
        a += 5

        b %= "fmt"
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Name("a", location=mock.ANY),
            Name("b", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_walrus(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        a = (b := 5)
        x = (y, z := 10)  # this is not `(y, z) := 10` but `y, (z := 10)`
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Name("a", location=mock.ANY),
            Name("b", location=mock.ANY),
            Name("x", location=mock.ANY),
            Name("z", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_walrus_lambda(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        outer_lambda = (inner_lambda := lambda *a, **k: 0)
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Func(
                name="inner_lambda",
                location=mock.ANY,
                interface=CallInterface(vararg="a", kwarg="k"),
            ),
            Func(
                name="outer_lambda",
                location=mock.ANY,
                interface=CallInterface(vararg="a", kwarg="k"),
            ),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_faux_walrus_lambda(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        outer_lambda = (a, inner_lambda := lambda *a, **k: 0)
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Func(
                name="inner_lambda",
                location=mock.ANY,
                interface=CallInterface(vararg="a", kwarg="k"),
            ),
            Name(name="outer_lambda", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_function_def(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        def fn_one(a, b):
            pass

        def fn_two(c):
            var = "i shouldn't be in the root context!"
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Func(
                name="fn_one",
                location=mock.ANY,
                interface=CallInterface(args=("a", "b")),
            ),
            Func(
                name="fn_two",
                location=mock.ANY,
                interface=CallInterface(args=("c",)),
            ),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_async_function_def(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        async def fn_one(a, b):
            pass

        async def fn_two(c):
            var = "i shouldn't be in the root context!"
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Func(
                name="fn_one",
                location=mock.ANY,
                interface=CallInterface(args=("a", "b")),
                is_async=True,
            ),
            Func(
                name="fn_two",
                location=mock.ANY,
                interface=CallInterface(args=("c",)),
                is_async=True,
            ),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_anonymous_lambda(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
    capfd: pytest.CaptureFixture[str],
):
    module_ast = parse(
        """
        lambda: 1
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)

    _, stderr = capfd.readouterr()
    assert match_output(stderr, ["top-level lambdas must be named"])


def test_root_context_lambda_named(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        x = lambda a, b: 1
        y: type = lambda: 1
        z = lambda *args: 1
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Func(
                "x",
                location=mock.ANY,
                interface=CallInterface(
                    args=(
                        "a",
                        "b",
                    )
                ),
            ),
            Func("y", location=mock.ANY, interface=CallInterface()),
            Func("z", location=mock.ANY, interface=CallInterface(vararg="args")),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_lambda_named_invalid_multiple_lhs_and_rhs(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
    capfd: pytest.CaptureFixture[str],
):
    module_ast = parse(
        """
        x, y = lambda a, b: 1, 2
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)

    _, stderr = capfd.readouterr()
    assert match_output(stderr, ["lambda assignment must be one-to-one"])


def test_root_context_lambda_named_invalid_multiple_lhs(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
    capfd: pytest.CaptureFixture[str],
):
    module_ast = parse(
        """
        x, y = lambda a: 1
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)

    _, stderr = capfd.readouterr()
    assert match_output(stderr, ["lambda assignment must be one-to-one"])


def test_root_context_lambda_named_invalid_multiple_rhs(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
    capfd: pytest.CaptureFixture[str],
):
    module_ast = parse(
        """
        x = lambda a, b: 1, 2
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)

    _, stderr = capfd.readouterr()
    assert match_output(stderr, ["lambda assignment must be one-to-one"])


def test_root_context_if(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        if some_variable == "some value":
            def fn(a):
                pass

            global_var = 40
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Func(name="fn", location=mock.ANY, interface=CallInterface(args=("a",))),
            Name(name="global_var", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_nested_if(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        if some_variable == "some value":
            if some_other_variable == "some other value":
                def fn(a):
                    pass

                global_var = 40
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Func(name="fn", location=mock.ANY, interface=CallInterface(args=("a",))),
            Name(name="global_var", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_for(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        for i in ITER:
            def fn(a):
                pass

            global_var = 40
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Func(name="fn", location=mock.ANY, interface=CallInterface(args=("a",))),
            Name(name="global_var", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_nested_for(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        for iter in ITER_OF_ITERS:
            for i in iter:
                def fn(a):
                    pass

                global_var = 40
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Func(name="fn", location=mock.ANY, interface=CallInterface(args=("a",))),
            Name(name="global_var", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_async_for(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        async for i in ITER:
            def fn(a):
                pass

            global_var = 40
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Func(name="fn", location=mock.ANY, interface=CallInterface(args=("a",))),
            Name(name="global_var", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_while(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        while True:
            def fn(a):
                pass

            global_var = 40
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Func(name="fn", location=mock.ANY, interface=CallInterface(args=("a",))),
            Name(name="global_var", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_nested_while(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        while True:
            while True:
                def fn(a):
                    pass

                global_var = 40
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Func(name="fn", location=mock.ANY, interface=CallInterface(args=("a",))),
            Name(name="global_var", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_try(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
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
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Name("global_a", location=mock.ANY),
            Name("global_b", location=mock.ANY),
            Name("global_c", location=mock.ANY),
            Name("global_d", location=mock.ANY),
            Name("global_e", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_nested_try(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
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
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Name("global_a", location=mock.ANY),
            Name("global_b", location=mock.ANY),
            Name("global_c", location=mock.ANY),
            Name("global_d", location=mock.ANY),
            Name("global_e", location=mock.ANY),
            Name("global_z", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_with(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        with context_manager() as ctx:
            def fn(a):
                pass

            global_var = 40
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Func(name="fn", location=mock.ANY, interface=CallInterface(args=("a",))),
            Name(name="global_var", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_nested_with(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        with context_manager() as ctx:
            with ctx() as inner_ctx:
                def fn(a):
                    pass

                global_var = 40
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Func(name="fn", location=mock.ANY, interface=CallInterface(args=("a",))),
            Name(name="global_var", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_async_with(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        async with context_manager() as ctx:
            def fn(a):
                pass

            global_var = 40
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Func(name="fn", location=mock.ANY, interface=CallInterface(args=("a",))),
            Name(name="global_var", location=mock.ANY),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_class_def(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    module_ast = parse(
        """
        class TopLevel:
            def __init__(self, a):
                self.a = a

            def method(self):
                var = "i shouldn't be in the root context!"
                return var + " see, i'm not!"
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [
            Class(
                name="TopLevel",
                location=mock.ANY,
                interface=CallInterface(
                    args=(
                        "self",
                        "a",
                    )
                ),
            ),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)


def test_root_context_module_level_docstring(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
    capfd: pytest.CaptureFixture[str],
):
    module_ast = parse(
        """
        '''
        Docstring at module level.
        '''
        """
    )
    context = compile_root_context(module_ast)
    expected = make_symbol_table(
        [],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)

    _, stderr = capfd.readouterr()
    assert match_output(stderr, [])


def test_root_context_module(
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
    capfd: pytest.CaptureFixture[str],
):
    module_ast = parse(
        """
        '''My module.'''
        from __future__ import annotations

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

    with mock.patch("sys.exit") as m_exit:
        context = compile_root_context(module_ast)

    expected = make_symbol_table(
        [
            Import(
                name="annotations",
                qualified_name="__future__.annotations",
                location=mock.ANY,
            ),
            Import(name="a_module", location=mock.ANY),
            Import(
                name="some_function",
                qualified_name="another_module.some_function",
                location=mock.ANY,
            ),
            Func(
                name="my_function",
                location=mock.ANY,
                interface=CallInterface(args=("a", "b")),
            ),
            Class(
                name="MyClass",
                location=mock.ANY,
                interface=CallInterface(args=("self",)),
            ),
        ],
        include_root_symbols=True,
    )

    assert context.parent is None
    assert compare_symbol_table_symbols(context.symbol_table, expected)

    assert m_exit.call_count == 2

    _, stderr = capfd.readouterr()
    assert match_output(
        stderr,
        [
            "unable to find module 'a_module'",
            "unable to find module 'another_module'",
        ],
    )
