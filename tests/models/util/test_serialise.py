from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from frozendict import frozendict

from rattr.models.context import Context, SymbolTable, compile_root_context
from rattr.models.ir import FileIr, FunctionIr
from rattr.models.results import FileResults, FunctionResults
from rattr.models.symbol import (
    AnyCallInterface,
    Builtin,
    Call,
    CallArguments,
    CallInterface,
    Class,
    Func,
    Import,
    Location,
    Name,
    Symbol,
    UserDefinedCallableSymbol,
)
from rattr.models.util import OutputIrs, deserialise, serialise, serialise_irs
from tests.models.util.shared import CallInterfaceArgs

if TYPE_CHECKING:
    from tests.shared import (
        MakeRootContextFn,
        MakeSymbolTableFn,
        OsDependentPathFn,
        ParseFn,
    )


@pytest.fixture
def symbol_group_one() -> list[Symbol]:
    return [
        Name("bob"),
        Func("my_func", interface=CallInterface(posonlyargs=("a", "b"))),
        Name("foo.bar.baz", "foo"),
    ]


@pytest.fixture
def symbol_group_two() -> list[Symbol]:
    return [
        Name("i.am.in.the.child.context", "i"),
        Func(
            "a_function_here",
            interface=CallInterface(args=("x", "y"), vararg="extras"),
        ),
    ]


@pytest.fixture
def simple_context_one(
    make_root_context: MakeRootContextFn,
    symbol_group_one: list[Symbol],
) -> Context:
    return make_root_context(symbol_group_one, include_root_symbols=False)


@pytest.fixture
def simple_context_two(
    make_root_context: MakeRootContextFn,
    symbol_group_two: list[Symbol],
) -> Context:
    return make_root_context(symbol_group_two, include_root_symbols=False)


@pytest.fixture
def nested_context(
    make_symbol_table: MakeSymbolTableFn,
    simple_context_one: Context,
    symbol_group_two: list[Symbol],
):
    return Context(
        parent=simple_context_one,
        symbol_table=make_symbol_table(symbol_group_two, include_root_symbols=False),
        file=Path("/some/other/file.py"),
    )


@pytest.fixture
def full_file_ir() -> dict[UserDefinedCallableSymbol, FunctionIr]:
    my_func_symbol = Func("my_func", interface=CallInterface(posonlyargs=("a", "b")))
    a_function_here_symbol = Func(
        "a_function_here",
        interface=CallInterface(args=("x", "y"), vararg="extras"),
    )
    my_class_symbol = Class(
        "MyClass",
        interface=CallInterface(
            args=("self", "data"),
            kwonlyargs=("kwarg_a", "kwarg_b"),
        ),
    )

    return {
        my_func_symbol: FunctionIr.new(
            gets={
                Name("a"),
                Name("b.bar.baz", "b"),
            }
        ),
        a_function_here_symbol: FunctionIr.new(
            gets={
                Name("foo"),
                Name("foo.bar.baz", "foo"),
            },
            calls={
                Call(
                    name=my_func_symbol.name,
                    args=CallArguments(args=("foo", "foo")),
                    target=my_func_symbol,
                ),
            },
        ),
        my_class_symbol: FunctionIr.new(
            gets={
                Name("self"),
                Name("data"),
                Name("kwarg_a"),
                Name("kwarg_b"),
            },
            sets={
                Name("self.data", "self"),
                Name("self._a", "self"),
                Name("self._b", "self"),
            },
        ),
    }


def test_name(parse: ParseFn, os_dependent_path: OsDependentPathFn):
    ast_module = parse(
        """
        def _():
            x = "bloop"
        """
    )
    ast_fn_def: ast.FunctionDef = ast_module.body[0]
    ast_assign: ast.Assign = ast_fn_def.body[0]
    ast_name: ast.Name = ast_assign.targets[0]

    name = Name("x", token=ast_name)

    serialised = serialise(name)
    assert json.loads(serialised) == {
        "type": "Name",
        "name": "x",
        "basename": "x",
        "location": {
            "lineno": 2,
            "end_lineno": 2,
            "col_offset": 4,
            "end_col_offset": 5,
            "file": os_dependent_path("test.py"),
        },
        "interface": None,
    }

    deserialised = deserialise(serialised, type=Symbol)
    assert deserialised == name


@pytest.mark.parametrize("builtin_name", ["print", "getattr"])
def test_builtin(builtin_name: str):
    builtin = Builtin(builtin_name)

    serialised = serialise(builtin)
    assert json.loads(serialised) == {
        "type": "Builtin",
        "name": builtin_name,
        "location": {
            "lineno": 1,
            "col_offset": 0,
            "end_lineno": None,
            "end_col_offset": None,
            "file": "built-in",
        },
        "interface": "any",
    }

    deserialised = deserialise(serialised, type=Builtin)
    assert deserialised == builtin


def test_import(parse: ParseFn, os_dependent_path: OsDependentPathFn):
    ast_module = parse(
        """
        from math import pi
        """
    )
    context = compile_root_context(ast_module)
    import_: Import = context.get("pi")

    serialised = serialise(import_)
    assert json.loads(serialised) == {
        "type": "Import",
        "name": "pi",
        "qualified_name": "math.pi",
        "location": {
            "lineno": 1,
            "col_offset": 0,
            "end_lineno": 1,
            "end_col_offset": 19,
            "file": os_dependent_path("test.py"),
        },
        "interface": "any",
    }

    deserialised = deserialise(serialised, type=Symbol)
    assert deserialised == import_


def test_import_multiple(parse: ParseFn, os_dependent_path: OsDependentPathFn):
    ast_module = parse(
        """
        '''Blah.'''
        import math as maths, os
        """
    )
    context = compile_root_context(ast_module)
    imports_: list[Import] = [
        context.get("maths"),
        context.get("os"),
    ]

    serialised = [serialise(import_) for import_ in imports_]
    assert [json.loads(s) for s in serialised] == [
        {
            "type": "Import",
            "name": "maths",
            "qualified_name": "math",
            "location": {
                "lineno": 2,
                "col_offset": 0,
                "end_lineno": 2,
                "end_col_offset": 24,
                "file": os_dependent_path("test.py"),
            },
            "interface": "any",
        },
        {
            "type": "Import",
            "name": "os",
            "qualified_name": "os",
            "location": {
                "lineno": 2,
                "col_offset": 0,
                "end_lineno": 2,
                "end_col_offset": 24,
                "file": os_dependent_path("test.py"),
            },
            "interface": "any",
        },
    ]

    deserialised = [deserialise(s, type=Symbol) for s in serialised]
    assert deserialised == imports_


def test_func(parse: ParseFn, os_dependent_path: OsDependentPathFn):
    ast_module = parse(
        """
        def func(a, /, b, c, *args, d = None, e = None, **kwargs):
            ...
        """
    )
    context = compile_root_context(ast_module)
    func: Func = context.get("func")

    serialised = serialise(func)
    assert json.loads(serialised) == {
        "type": "Func",
        "name": "func",
        "location": {
            "lineno": 1,
            "col_offset": 0,
            "end_lineno": 2,
            "end_col_offset": 7,
            "file": os_dependent_path("test.py"),
        },
        "interface": {
            "posonlyargs": ["a"],
            "args": ["b", "c"],
            "vararg": "args",
            "kwonlyargs": ["d", "e"],
            "kwarg": "kwargs",
        },
        "is_async": False,
    }

    deserialised = deserialise(serialised, type=Symbol)
    assert deserialised == func


def test_class(parse: ParseFn, os_dependent_path: OsDependentPathFn):
    ast_module = parse(
        """
        class ParentClass:
            ...

        class MyClass(ParentClass):
            ...
        """
    )
    context = compile_root_context(ast_module)
    cls: Class = context.get("MyClass")

    serialised = serialise(cls)
    assert json.loads(serialised) == {
        "type": "Class",
        "name": "MyClass",
        "location": {
            "lineno": 4,
            "col_offset": 0,
            "end_lineno": 5,
            "end_col_offset": 7,
            "file": os_dependent_path("test.py"),
        },
        "interface": "any",
    }

    deserialised = deserialise(serialised, type=Symbol)
    assert deserialised == cls


def test_call(parse: ParseFn, os_dependent_path: OsDependentPathFn):
    ast_module = parse(
        """
        def some_func(a: int, b: int, **kwargs):
            ...

        y = ...
        x = some_func(y.some_attr, y.nested.attr)
        """
    )
    context = compile_root_context(ast_module)
    func: Func = context.get("some_func")
    call = Call(
        name="some_func",
        args=CallArguments(args=("y.some_attr", "y.nested.attr")),
        target=func,
    )

    serialised = serialise(call)
    assert json.loads(serialised) == {
        "type": "Call",
        "name": "some_func",
        "args": {"args": ["y.some_attr", "y.nested.attr"], "kwargs": {}},
        "target": {
            "type": "Func",
            "name": "some_func",
            "location": {
                "lineno": 1,
                "col_offset": 0,
                "end_lineno": 2,
                "end_col_offset": 7,
                "file": os_dependent_path("test.py"),
            },
            "interface": {
                "posonlyargs": [],
                "args": ["a", "b"],
                "vararg": None,
                "kwonlyargs": [],
                "kwarg": "kwargs",
            },
            "is_async": False,
        },
        "location": {
            "lineno": 1,
            "col_offset": 0,
            "end_lineno": None,
            "end_col_offset": None,
            "file": os_dependent_path("test.py"),
        },
    }

    deserialised = deserialise(serialised, type=Symbol)
    assert deserialised == call


@pytest.mark.parametrize(
    "as_tuple",
    testcases := [
        # the empty signature
        CallInterfaceArgs([], [], None, [], None),
        # just args and kwargs
        CallInterfaceArgs([], [], "args", [], None),
        CallInterfaceArgs([], [], None, [], "kwargs"),
        CallInterfaceArgs([], [], "args", [], "kwargs"),
        # posonlyargs
        CallInterfaceArgs(["a"], [], None, [], None),
        CallInterfaceArgs(["a", "b"], [], None, [], None),
        CallInterfaceArgs(["a"], [], "args", [], None),
        # args
        CallInterfaceArgs([], ["a"], None, [], None),
        CallInterfaceArgs([], ["a", "b"], None, [], None),
        CallInterfaceArgs([], ["a"], "args", [], None),
        # kwonlyargs
        CallInterfaceArgs([], [], None, ["a"], None),
        CallInterfaceArgs([], [], None, ["a", "b"], None),
        CallInterfaceArgs([], [], "args", ["a"], None),
        # mixed
        CallInterfaceArgs(["a", "b"], ["c", "d", "e"], "args", ["f", "g"], "kwargs"),
    ],
    ids=[i for i, _ in enumerate(testcases)],
)
def test_call_interface(as_tuple: CallInterfaceArgs):
    interface = CallInterface(*as_tuple)

    serialised = serialise(interface)
    assert json.loads(serialised) == {
        "posonlyargs": as_tuple.posonlyargs,
        "args": as_tuple.args,
        "vararg": as_tuple.vararg,
        "kwonlyargs": as_tuple.kwonlyargs,
        "kwarg": as_tuple.kwarg,
    }

    deserialised = deserialise(serialised, type=CallInterface)
    assert deserialised == interface

    # When serialise the tuple becomes a list, so ensure that on deserialisation this is
    # reversed
    assert isinstance(deserialised.posonlyargs, tuple)
    assert isinstance(deserialised.args, tuple)
    assert isinstance(deserialised.kwonlyargs, tuple)


def test_any_call_interface():
    interface = AnyCallInterface()

    serialised = serialise(interface)
    assert serialised == '"any"'

    deserialised = deserialise(serialised, type=AnyCallInterface)
    assert deserialised == interface


def test_any_call_interface_as_call_interface():
    interface = AnyCallInterface()

    serialised = serialise(interface)
    assert serialised == '"any"'

    deserialised = deserialise(serialised, type=CallInterface)
    assert deserialised == interface


@pytest.mark.parametrize(
    "args, kwargs",
    [
        ((), {}),
        (("a",), {}),
        (("a", "b"), {}),
        ((), {"A": "a"}),
        ((), {"A": "a", "B": "b"}),
        (("a", "b"), {"C": "c", "D": "d"}),
    ],
)
def test_call_arguments(args: tuple[str, ...], kwargs: dict[str, str]):
    call_arguments = CallArguments(args=args, kwargs=kwargs)

    serialised = serialise(call_arguments)
    assert json.loads(serialised) == {
        "args": list(args),
        "kwargs": kwargs,
    }

    deserialised = deserialise(serialised, type=CallArguments)
    assert deserialised == call_arguments

    assert isinstance(deserialised.args, tuple)
    assert isinstance(deserialised.kwargs, frozendict)


def test_location(os_dependent_path: OsDependentPathFn):
    location = Location(
        lineno=123,
        col_offset=50,
        end_lineno=128,
        end_col_offset=1,
        file=Path("/path/to/the/file.py"),
    )

    serialised = serialise(location)
    assert json.loads(serialised) == {
        "lineno": 123,
        "end_lineno": 128,
        "col_offset": 50,
        "end_col_offset": 1,
        "file": os_dependent_path("/path/to/the/file.py"),
    }

    deserialised = deserialise(serialised, type=Location)
    assert deserialised == location
    assert isinstance(deserialised.file, Path)


def test_location_ast_from_token(os_dependent_path: OsDependentPathFn):
    token = ast.parse("x = 123").body[0]
    location = Location.from_ast_token(token, file=Path("/path/to/the/file.py"))

    serialised = serialise(location)
    assert json.loads(serialised) == {
        "lineno": 1,
        "end_lineno": 1,
        "col_offset": 0,
        "end_col_offset": 7,
        "file": os_dependent_path("/path/to/the/file.py"),
    }

    deserialised = deserialise(serialised, type=Location)
    assert deserialised == location


def test_the_empty_symbol_table(make_symbol_table: MakeSymbolTableFn):
    symbol_table = make_symbol_table([], include_root_symbols=False)
    assert symbol_table._symbols == {}

    serialised = serialise(symbol_table)
    assert json.loads(serialised) == {}

    deserialised = deserialise(serialised, type=SymbolTable)
    assert deserialised == symbol_table


def test_symbol_table(
    make_symbol_table: MakeSymbolTableFn,
    symbol_group_one: list[Symbol],
    os_dependent_path: OsDependentPathFn,
):
    symbol_table = make_symbol_table(symbol_group_one, include_root_symbols=False)
    assert symbol_table._symbols != {}

    serialised = serialise(symbol_table)
    assert json.loads(serialised) == {
        "bob": {
            "type": "Name",
            "name": "bob",
            "basename": "bob",
            "location": {
                "lineno": 1,
                "col_offset": 0,
                "end_lineno": None,
                "end_col_offset": None,
                "file": os_dependent_path("test.py"),
            },
            "interface": None,
        },
        "my_func": {
            "type": "Func",
            "name": "my_func",
            "location": {
                "lineno": 1,
                "col_offset": 0,
                "end_lineno": None,
                "end_col_offset": None,
                "file": os_dependent_path("test.py"),
            },
            "interface": {
                "posonlyargs": ["a", "b"],
                "args": [],
                "vararg": None,
                "kwonlyargs": [],
                "kwarg": None,
            },
            "is_async": False,
        },
        "foo.bar.baz": {
            "type": "Name",
            "name": "foo.bar.baz",
            "basename": "foo",
            "location": {
                "lineno": 1,
                "col_offset": 0,
                "end_lineno": None,
                "end_col_offset": None,
                "file": os_dependent_path("test.py"),
            },
            "interface": None,
        },
    }

    deserialised = deserialise(serialised, type=SymbolTable)
    assert deserialised == symbol_table


def test_the_empty_context(
    make_root_context: MakeRootContextFn,
    os_dependent_path: OsDependentPathFn,
):
    context = make_root_context([], include_root_symbols=False)
    assert context.symbol_table._symbols == {}

    serialised = serialise(context)
    assert json.loads(serialised) == {
        "parent": None,
        "symbol_table": {},
        "file": os_dependent_path("test.py"),
    }

    deserialised = deserialise(serialised, type=Context)
    assert deserialised == context


def test_context(
    simple_context_one: Context,
    os_dependent_path: OsDependentPathFn,
):
    assert simple_context_one.symbol_table._symbols != {}

    serialised = serialise(simple_context_one)
    assert json.loads(serialised) == {
        "parent": None,
        "symbol_table": {
            "bob": {
                "type": "Name",
                "name": "bob",
                "basename": "bob",
                "location": {
                    "lineno": 1,
                    "col_offset": 0,
                    "end_lineno": None,
                    "end_col_offset": None,
                    "file": os_dependent_path("test.py"),
                },
                "interface": None,
            },
            "my_func": {
                "type": "Func",
                "name": "my_func",
                "location": {
                    "lineno": 1,
                    "col_offset": 0,
                    "end_lineno": None,
                    "end_col_offset": None,
                    "file": os_dependent_path("test.py"),
                },
                "interface": {
                    "posonlyargs": ["a", "b"],
                    "args": [],
                    "vararg": None,
                    "kwonlyargs": [],
                    "kwarg": None,
                },
                "is_async": False,
            },
            "foo.bar.baz": {
                "type": "Name",
                "name": "foo.bar.baz",
                "basename": "foo",
                "location": {
                    "lineno": 1,
                    "col_offset": 0,
                    "end_lineno": None,
                    "end_col_offset": None,
                    "file": os_dependent_path("test.py"),
                },
                "interface": None,
            },
        },
        "file": os_dependent_path("test.py"),
    }

    deserialised = deserialise(serialised, type=Context)
    assert deserialised == simple_context_one


def test_context_with_parent(
    nested_context: Context,
    os_dependent_path: OsDependentPathFn,
):
    serialised = serialise(nested_context)
    assert json.loads(serialised) == {
        "parent": {
            "parent": None,
            "symbol_table": {
                "bob": {
                    "type": "Name",
                    "name": "bob",
                    "basename": "bob",
                    "location": {
                        "lineno": 1,
                        "col_offset": 0,
                        "end_lineno": None,
                        "end_col_offset": None,
                        "file": os_dependent_path("test.py"),
                    },
                    "interface": None,
                },
                "my_func": {
                    "type": "Func",
                    "name": "my_func",
                    "location": {
                        "lineno": 1,
                        "col_offset": 0,
                        "end_lineno": None,
                        "end_col_offset": None,
                        "file": os_dependent_path("test.py"),
                    },
                    "interface": {
                        "posonlyargs": ["a", "b"],
                        "args": [],
                        "vararg": None,
                        "kwonlyargs": [],
                        "kwarg": None,
                    },
                    "is_async": False,
                },
                "foo.bar.baz": {
                    "type": "Name",
                    "name": "foo.bar.baz",
                    "basename": "foo",
                    "location": {
                        "lineno": 1,
                        "col_offset": 0,
                        "end_lineno": None,
                        "end_col_offset": None,
                        "file": os_dependent_path("test.py"),
                    },
                    "interface": None,
                },
            },
            "file": os_dependent_path("test.py"),
        },
        "symbol_table": {
            "i.am.in.the.child.context": {
                "type": "Name",
                "name": "i.am.in.the.child.context",
                "basename": "i",
                "location": {
                    "lineno": 1,
                    "col_offset": 0,
                    "end_lineno": None,
                    "end_col_offset": None,
                    "file": os_dependent_path("test.py"),
                },
                "interface": None,
            },
            "a_function_here": {
                "type": "Func",
                "name": "a_function_here",
                "location": {
                    "lineno": 1,
                    "col_offset": 0,
                    "end_lineno": None,
                    "end_col_offset": None,
                    "file": os_dependent_path("test.py"),
                },
                "interface": {
                    "posonlyargs": [],
                    "args": ["x", "y"],
                    "vararg": "extras",
                    "kwonlyargs": [],
                    "kwarg": None,
                },
                "is_async": False,
            },
        },
        "file": os_dependent_path("/some/other/file.py"),
    }

    deserialised = deserialise(serialised, type=Context)
    assert deserialised == nested_context


def test_the_empty_file_ir():
    file_ir = FileIr(context=None, file_ir={})

    serialised = serialise(file_ir)
    assert json.loads(serialised) == {
        "context": None,
        "symbols": {},
        "function_irs": {},
    }

    deserialised = deserialise(serialised, type=FileIr)
    assert deserialised == file_ir


def test_file_ir(
    nested_context: Context,
    full_file_ir: dict[UserDefinedCallableSymbol, FunctionIr],
    os_dependent_path: OsDependentPathFn,
):
    file_ir = FileIr(context=nested_context, file_ir=full_file_ir)

    serialised = serialise(file_ir)
    assert json.loads(serialised) == {
        "context": {
            "parent": {
                "parent": None,
                "symbol_table": {
                    "bob": {
                        "type": "Name",
                        "name": "bob",
                        "basename": "bob",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": None,
                    },
                    "my_func": {
                        "type": "Func",
                        "name": "my_func",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": {
                            "posonlyargs": ["a", "b"],
                            "args": [],
                            "vararg": None,
                            "kwonlyargs": [],
                            "kwarg": None,
                        },
                        "is_async": False,
                    },
                    "foo.bar.baz": {
                        "type": "Name",
                        "name": "foo.bar.baz",
                        "basename": "foo",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": None,
                    },
                },
                "file": os_dependent_path("test.py"),
            },
            "symbol_table": {
                "i.am.in.the.child.context": {
                    "type": "Name",
                    "name": "i.am.in.the.child.context",
                    "basename": "i",
                    "location": {
                        "lineno": 1,
                        "col_offset": 0,
                        "end_lineno": None,
                        "end_col_offset": None,
                        "file": os_dependent_path("test.py"),
                    },
                    "interface": None,
                },
                "a_function_here": {
                    "type": "Func",
                    "name": "a_function_here",
                    "location": {
                        "lineno": 1,
                        "col_offset": 0,
                        "end_lineno": None,
                        "end_col_offset": None,
                        "file": os_dependent_path("test.py"),
                    },
                    "interface": {
                        "posonlyargs": [],
                        "args": ["x", "y"],
                        "vararg": "extras",
                        "kwonlyargs": [],
                        "kwarg": None,
                    },
                    "is_async": False,
                },
            },
            "file": os_dependent_path("/some/other/file.py"),
        },
        "symbols": {
            "my_func": {
                "type": "Func",
                "name": "my_func",
                "location": {
                    "lineno": 1,
                    "col_offset": 0,
                    "end_lineno": None,
                    "end_col_offset": None,
                    "file": os_dependent_path("test.py"),
                },
                "interface": {
                    "posonlyargs": ["a", "b"],
                    "args": [],
                    "vararg": None,
                    "kwonlyargs": [],
                    "kwarg": None,
                },
                "is_async": False,
            },
            "a_function_here": {
                "type": "Func",
                "name": "a_function_here",
                "location": {
                    "lineno": 1,
                    "col_offset": 0,
                    "end_lineno": None,
                    "end_col_offset": None,
                    "file": os_dependent_path("test.py"),
                },
                "interface": {
                    "posonlyargs": [],
                    "args": ["x", "y"],
                    "vararg": "extras",
                    "kwonlyargs": [],
                    "kwarg": None,
                },
                "is_async": False,
            },
            "MyClass": {
                "type": "Class",
                "name": "MyClass",
                "location": {
                    "lineno": 1,
                    "col_offset": 0,
                    "end_lineno": None,
                    "end_col_offset": None,
                    "file": os_dependent_path("test.py"),
                },
                "interface": {
                    "posonlyargs": [],
                    "args": ["self", "data"],
                    "vararg": None,
                    "kwonlyargs": ["kwarg_a", "kwarg_b"],
                    "kwarg": None,
                },
            },
        },
        "function_irs": {
            "MyClass": {
                "gets": [
                    {
                        "type": "Name",
                        "name": "data",
                        "basename": "data",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": None,
                    },
                    {
                        "type": "Name",
                        "name": "kwarg_a",
                        "basename": "kwarg_a",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": None,
                    },
                    {
                        "type": "Name",
                        "name": "kwarg_b",
                        "basename": "kwarg_b",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": None,
                    },
                    {
                        "type": "Name",
                        "name": "self",
                        "basename": "self",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": None,
                    },
                ],
                "sets": [
                    {
                        "type": "Name",
                        "name": "self._a",
                        "basename": "self",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": None,
                    },
                    {
                        "type": "Name",
                        "name": "self._b",
                        "basename": "self",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": None,
                    },
                    {
                        "type": "Name",
                        "name": "self.data",
                        "basename": "self",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": None,
                    },
                ],
                "dels": [],
                "calls": [],
            },
            "a_function_here": {
                "gets": [
                    {
                        "type": "Name",
                        "name": "foo",
                        "basename": "foo",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": None,
                    },
                    {
                        "type": "Name",
                        "name": "foo.bar.baz",
                        "basename": "foo",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": None,
                    },
                ],
                "sets": [],
                "dels": [],
                "calls": [
                    {
                        "type": "Call",
                        "name": "my_func",
                        "args": {"args": ["foo", "foo"], "kwargs": {}},
                        "target": {
                            "type": "Func",
                            "name": "my_func",
                            "location": {
                                "lineno": 1,
                                "col_offset": 0,
                                "end_lineno": None,
                                "end_col_offset": None,
                                "file": os_dependent_path("test.py"),
                            },
                            "interface": {
                                "posonlyargs": ["a", "b"],
                                "args": [],
                                "vararg": None,
                                "kwonlyargs": [],
                                "kwarg": None,
                            },
                            "is_async": False,
                        },
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                    }
                ],
            },
            "my_func": {
                "gets": [
                    {
                        "type": "Name",
                        "name": "a",
                        "basename": "a",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": None,
                    },
                    {
                        "type": "Name",
                        "name": "b.bar.baz",
                        "basename": "b",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": None,
                    },
                ],
                "sets": [],
                "dels": [],
                "calls": [],
            },
        },
    }

    deserialised = deserialise(serialised, type=FileIr)
    assert deserialised == file_ir


def test_the_empty_output_irs():
    output_irs = OutputIrs(
        import_irs={},
        target_ir={"filename": "file.py", "ir": FileIr(context=None, file_ir={})},
    )

    serialised = serialise_irs(
        target_name="file.py",
        target_ir=FileIr(context=None, file_ir={}),
        import_irs={},
    )
    assert json.loads(serialised) == {
        "import_irs": {},
        "target_ir": {
            "filename": "file.py",
            "ir": {"context": None, "function_irs": {}, "symbols": {}},
        },
    }

    deserialised = deserialise(serialised, type=OutputIrs)
    assert deserialised == output_irs


def test_output_irs(
    full_file_ir: dict[UserDefinedCallableSymbol, FunctionIr],
    nested_context: Context,
    simple_context_one: Context,
    simple_context_two: Context,
    os_dependent_path: OsDependentPathFn,
):
    output_irs = OutputIrs(
        import_irs={
            "some.module": FileIr(
                context=simple_context_one,
                file_ir={
                    (
                        my_func := Func(
                            "my_func",
                            interface=CallInterface(posonlyargs=("a", "b")),
                        )
                    ): FunctionIr.new(
                        gets={
                            Name("a"),
                            Name("a.attr"),
                            Name("b.another_attr"),
                            Name("a.thing"),
                        },
                        sets={
                            Name("local"),
                        },
                    ),
                    Func(
                        "my_func_two",
                        interface=CallInterface(posonlyargs=("arg",)),
                    ): FunctionIr.new(
                        gets={
                            Name("arg"),
                            Name("arg.attr"),
                            Name("arg.another_attr"),
                            Name("arg.thing"),
                        },
                        sets={
                            Name("local"),
                        },
                        calls={
                            Call(
                                name="my_func",
                                args=CallArguments(args=("arg", "arg")),
                                target=my_func,
                            )
                        },
                    ),
                },
            ),
            "another.module.here": FileIr(
                context=simple_context_two,
                file_ir={
                    Func(
                        "a_function_here",
                        interface=CallInterface(args=("x", "y"), vararg="extras"),
                    ): FunctionIr.new(
                        gets={
                            Name("x"),
                            Name("y"),
                            Name("x.a.b.c.d"),
                        },
                    ),
                },
            ),
            "an_empty_module": FileIr(context=None, file_ir={}),
        },
        target_ir={
            "filename": "file.py",
            "ir": FileIr(context=nested_context, file_ir=full_file_ir),
        },
    )

    serialised = serialise_irs(
        target_name=output_irs.target_ir["filename"],
        target_ir=output_irs.target_ir["ir"],
        import_irs=output_irs.import_irs,
    )
    assert json.loads(serialised) == {
        "import_irs": {
            "some.module": {
                "context": {
                    "parent": None,
                    "symbol_table": {
                        "bob": {
                            "type": "Name",
                            "name": "bob",
                            "basename": "bob",
                            "location": {
                                "lineno": 1,
                                "col_offset": 0,
                                "end_lineno": None,
                                "end_col_offset": None,
                                "file": os_dependent_path("test.py"),
                            },
                            "interface": None,
                        },
                        "my_func": {
                            "type": "Func",
                            "name": "my_func",
                            "location": {
                                "lineno": 1,
                                "col_offset": 0,
                                "end_lineno": None,
                                "end_col_offset": None,
                                "file": os_dependent_path("test.py"),
                            },
                            "interface": {
                                "posonlyargs": ["a", "b"],
                                "args": [],
                                "vararg": None,
                                "kwonlyargs": [],
                                "kwarg": None,
                            },
                            "is_async": False,
                        },
                        "foo.bar.baz": {
                            "type": "Name",
                            "name": "foo.bar.baz",
                            "basename": "foo",
                            "location": {
                                "lineno": 1,
                                "col_offset": 0,
                                "end_lineno": None,
                                "end_col_offset": None,
                                "file": os_dependent_path("test.py"),
                            },
                            "interface": None,
                        },
                    },
                    "file": os_dependent_path("test.py"),
                },
                "symbols": {
                    "my_func": {
                        "type": "Func",
                        "name": "my_func",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": {
                            "posonlyargs": ["a", "b"],
                            "args": [],
                            "vararg": None,
                            "kwonlyargs": [],
                            "kwarg": None,
                        },
                        "is_async": False,
                    },
                    "my_func_two": {
                        "type": "Func",
                        "name": "my_func_two",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": {
                            "posonlyargs": ["arg"],
                            "args": [],
                            "vararg": None,
                            "kwonlyargs": [],
                            "kwarg": None,
                        },
                        "is_async": False,
                    },
                },
                "function_irs": {
                    "my_func": {
                        "gets": [
                            {
                                "type": "Name",
                                "name": "a",
                                "basename": "a",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                            {
                                "type": "Name",
                                "name": "a.attr",
                                "basename": "a",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                            {
                                "type": "Name",
                                "name": "a.thing",
                                "basename": "a",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                            {
                                "type": "Name",
                                "name": "b.another_attr",
                                "basename": "b",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                        ],
                        "sets": [
                            {
                                "type": "Name",
                                "name": "local",
                                "basename": "local",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            }
                        ],
                        "dels": [],
                        "calls": [],
                    },
                    "my_func_two": {
                        "gets": [
                            {
                                "type": "Name",
                                "name": "arg",
                                "basename": "arg",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                            {
                                "type": "Name",
                                "name": "arg.another_attr",
                                "basename": "arg",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                            {
                                "type": "Name",
                                "name": "arg.attr",
                                "basename": "arg",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                            {
                                "type": "Name",
                                "name": "arg.thing",
                                "basename": "arg",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                        ],
                        "sets": [
                            {
                                "type": "Name",
                                "name": "local",
                                "basename": "local",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            }
                        ],
                        "dels": [],
                        "calls": [
                            {
                                "type": "Call",
                                "name": "my_func",
                                "args": {"args": ["arg", "arg"], "kwargs": {}},
                                "target": {
                                    "type": "Func",
                                    "name": "my_func",
                                    "location": {
                                        "lineno": 1,
                                        "col_offset": 0,
                                        "end_lineno": None,
                                        "end_col_offset": None,
                                        "file": os_dependent_path("test.py"),
                                    },
                                    "interface": {
                                        "posonlyargs": ["a", "b"],
                                        "args": [],
                                        "vararg": None,
                                        "kwonlyargs": [],
                                        "kwarg": None,
                                    },
                                    "is_async": False,
                                },
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                            }
                        ],
                    },
                },
            },
            "another.module.here": {
                "context": {
                    "parent": None,
                    "symbol_table": {
                        "i.am.in.the.child.context": {
                            "type": "Name",
                            "name": "i.am.in.the.child.context",
                            "basename": "i",
                            "location": {
                                "lineno": 1,
                                "col_offset": 0,
                                "end_lineno": None,
                                "end_col_offset": None,
                                "file": os_dependent_path("test.py"),
                            },
                            "interface": None,
                        },
                        "a_function_here": {
                            "type": "Func",
                            "name": "a_function_here",
                            "location": {
                                "lineno": 1,
                                "col_offset": 0,
                                "end_lineno": None,
                                "end_col_offset": None,
                                "file": os_dependent_path("test.py"),
                            },
                            "interface": {
                                "posonlyargs": [],
                                "args": ["x", "y"],
                                "vararg": "extras",
                                "kwonlyargs": [],
                                "kwarg": None,
                            },
                            "is_async": False,
                        },
                    },
                    "file": os_dependent_path("test.py"),
                },
                "symbols": {
                    "a_function_here": {
                        "type": "Func",
                        "name": "a_function_here",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": {
                            "posonlyargs": [],
                            "args": ["x", "y"],
                            "vararg": "extras",
                            "kwonlyargs": [],
                            "kwarg": None,
                        },
                        "is_async": False,
                    }
                },
                "function_irs": {
                    "a_function_here": {
                        "gets": [
                            {
                                "type": "Name",
                                "name": "x",
                                "basename": "x",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                            {
                                "type": "Name",
                                "name": "x.a.b.c.d",
                                "basename": "x",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                            {
                                "type": "Name",
                                "name": "y",
                                "basename": "y",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                        ],
                        "sets": [],
                        "dels": [],
                        "calls": [],
                    }
                },
            },
            "an_empty_module": {"context": None, "symbols": {}, "function_irs": {}},
        },
        "target_ir": {
            "filename": "file.py",
            "ir": {
                "context": {
                    "parent": {
                        "parent": None,
                        "symbol_table": {
                            "bob": {
                                "type": "Name",
                                "name": "bob",
                                "basename": "bob",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                            "my_func": {
                                "type": "Func",
                                "name": "my_func",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": {
                                    "posonlyargs": ["a", "b"],
                                    "args": [],
                                    "vararg": None,
                                    "kwonlyargs": [],
                                    "kwarg": None,
                                },
                                "is_async": False,
                            },
                            "foo.bar.baz": {
                                "type": "Name",
                                "name": "foo.bar.baz",
                                "basename": "foo",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                        },
                        "file": os_dependent_path("test.py"),
                    },
                    "symbol_table": {
                        "i.am.in.the.child.context": {
                            "type": "Name",
                            "name": "i.am.in.the.child.context",
                            "basename": "i",
                            "location": {
                                "lineno": 1,
                                "col_offset": 0,
                                "end_lineno": None,
                                "end_col_offset": None,
                                "file": os_dependent_path("test.py"),
                            },
                            "interface": None,
                        },
                        "a_function_here": {
                            "type": "Func",
                            "name": "a_function_here",
                            "location": {
                                "lineno": 1,
                                "col_offset": 0,
                                "end_lineno": None,
                                "end_col_offset": None,
                                "file": os_dependent_path("test.py"),
                            },
                            "interface": {
                                "posonlyargs": [],
                                "args": ["x", "y"],
                                "vararg": "extras",
                                "kwonlyargs": [],
                                "kwarg": None,
                            },
                            "is_async": False,
                        },
                    },
                    "file": os_dependent_path("/some/other/file.py"),
                },
                "symbols": {
                    "MyClass": {
                        "type": "Class",
                        "name": "MyClass",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": {
                            "posonlyargs": [],
                            "args": ["self", "data"],
                            "vararg": None,
                            "kwonlyargs": ["kwarg_a", "kwarg_b"],
                            "kwarg": None,
                        },
                    },
                    "a_function_here": {
                        "type": "Func",
                        "name": "a_function_here",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": {
                            "posonlyargs": [],
                            "args": ["x", "y"],
                            "vararg": "extras",
                            "kwonlyargs": [],
                            "kwarg": None,
                        },
                        "is_async": False,
                    },
                    "my_func": {
                        "type": "Func",
                        "name": "my_func",
                        "location": {
                            "lineno": 1,
                            "col_offset": 0,
                            "end_lineno": None,
                            "end_col_offset": None,
                            "file": os_dependent_path("test.py"),
                        },
                        "interface": {
                            "posonlyargs": ["a", "b"],
                            "args": [],
                            "vararg": None,
                            "kwonlyargs": [],
                            "kwarg": None,
                        },
                        "is_async": False,
                    },
                },
                "function_irs": {
                    "MyClass": {
                        "gets": [
                            {
                                "type": "Name",
                                "name": "data",
                                "basename": "data",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                            {
                                "type": "Name",
                                "name": "kwarg_a",
                                "basename": "kwarg_a",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                            {
                                "type": "Name",
                                "name": "kwarg_b",
                                "basename": "kwarg_b",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                            {
                                "type": "Name",
                                "name": "self",
                                "basename": "self",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                        ],
                        "sets": [
                            {
                                "type": "Name",
                                "name": "self._a",
                                "basename": "self",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                            {
                                "type": "Name",
                                "name": "self._b",
                                "basename": "self",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                            {
                                "type": "Name",
                                "name": "self.data",
                                "basename": "self",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                        ],
                        "dels": [],
                        "calls": [],
                    },
                    "a_function_here": {
                        "gets": [
                            {
                                "type": "Name",
                                "name": "foo",
                                "basename": "foo",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                            {
                                "type": "Name",
                                "name": "foo.bar.baz",
                                "basename": "foo",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                        ],
                        "sets": [],
                        "dels": [],
                        "calls": [
                            {
                                "type": "Call",
                                "name": "my_func",
                                "args": {"args": ["foo", "foo"], "kwargs": {}},
                                "target": {
                                    "type": "Func",
                                    "name": "my_func",
                                    "location": {
                                        "lineno": 1,
                                        "col_offset": 0,
                                        "end_lineno": None,
                                        "end_col_offset": None,
                                        "file": os_dependent_path("test.py"),
                                    },
                                    "interface": {
                                        "posonlyargs": ["a", "b"],
                                        "args": [],
                                        "vararg": None,
                                        "kwonlyargs": [],
                                        "kwarg": None,
                                    },
                                    "is_async": False,
                                },
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                            }
                        ],
                    },
                    "my_func": {
                        "gets": [
                            {
                                "type": "Name",
                                "name": "a",
                                "basename": "a",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                            {
                                "type": "Name",
                                "name": "b.bar.baz",
                                "basename": "b",
                                "location": {
                                    "lineno": 1,
                                    "col_offset": 0,
                                    "end_lineno": None,
                                    "end_col_offset": None,
                                    "file": os_dependent_path("test.py"),
                                },
                                "interface": None,
                            },
                        ],
                        "sets": [],
                        "dels": [],
                        "calls": [],
                    },
                },
            },
        },
    }

    deserialised = deserialise(serialised, type=OutputIrs)
    assert deserialised == output_irs


def test_the_empty_file_results():
    results = FileResults({})

    serialised = serialise(results)
    assert json.loads(serialised) == {}

    deserialised = deserialise(serialised, type=FileResults)
    assert deserialised == results


def test_file_results():
    results = FileResults(
        {
            "foo": FunctionResults.the_empty_results(),
            "bar": FunctionResults.new(
                gets={"arg", "arg.attr"},
                calls={"foo"},
            ),
            "baz": FunctionResults.new(
                gets={
                    "x",
                    "x.attr",
                    "y",
                    "y.attr",
                    "x.some_flag",
                    "y.set_me",
                },
                sets={
                    "y.set_me",
                },
                dels={
                    "del_me",
                },
                calls={
                    "foo",
                    "bar",
                },
            ),
        }
    )

    serialised = serialise(results)
    assert json.loads(serialised) == {
        "bar": {"gets": ["arg", "arg.attr"], "sets": [], "dels": [], "calls": ["foo"]},
        "baz": {
            "gets": ["x", "x.attr", "x.some_flag", "y", "y.attr", "y.set_me"],
            "sets": ["y.set_me"],
            "dels": ["del_me"],
            "calls": ["bar", "foo"],
        },
        "foo": {"gets": [], "sets": [], "dels": [], "calls": []},
    }

    deserialised = deserialise(serialised, type=FileResults)
    assert deserialised == results
