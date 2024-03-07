from __future__ import annotations

import ast
from importlib.util import find_spec
from pathlib import Path

import pytest

from rattr.models.symbol import (
    PYTHON_ATTR_ACCESS_BUILTINS,
    PYTHON_BUILTINS,
    AnyCallInterface,
    Builtin,
    Call,
    CallArguments,
    CallInterface,
    Class,
    Func,
    Import,
    Name,
    Symbol,
)
from rattr.module_locator.models import ModuleSpec
from rattr.module_locator.util import format_origin_for_os


class TestAttrsDerivedProperties:
    def test_eq_on_equivalent(self):
        assert Name("a") == Name("a")
        assert Name("a") == Name("a", "a")

    def test_eq_on_non_equivalent(self):
        assert Name("a") != Name("b")
        assert Name("a") != Name("a", "b")
        assert Name("a") != Import("a")

    def test_hash_on_identical(self):
        assert hash(Name("a")) == hash(Name("a"))

    def test_hash_on_equivalent(self):
        assert hash(Name("a")) == hash(Name("a", "a"))

    def test_hash_on_non_equivalent(self):
        assert hash(Name("a")) != hash(Name("b"))
        assert hash(Name("a")) != hash(Name("a", "b"))
        assert hash(Name("a")) != hash(Import("a"))

    @pytest.mark.parametrize(
        "symbol_fixture",
        [
            "simple_name",
            "simple_builtin",
            "simple_import",
            "simple_func",
            "simple_class",
            "simple_call",
        ],
    )
    def test_is_hashable(self, symbol_fixture: str, request: pytest.FixtureRequest):
        # It was observed that the derived hash may fail if an attribute type is
        # non-hashable
        symbol: Symbol = request.getfixturevalue(symbol_fixture)
        assert isinstance(hash(symbol), int)


class TestId:
    @pytest.mark.parametrize(
        "symbol_fixture",
        ["simple_name", "simple_builtin", "simple_func", "simple_class", "simple_call"],
    )
    def test_id(self, symbol_fixture: str, request: pytest.FixtureRequest):
        symbol: Symbol = request.getfixturevalue(symbol_fixture)
        assert symbol.id == symbol.name

    def test_id_for_direct_import(self):
        assert Import(name="pi", qualified_name="math.pi").id == "pi"

    def test_id_for_starred_import(self):
        assert Import(name="*", qualified_name="math").id == "math.*"


class TestIsCallable:
    @pytest.mark.parametrize(
        "symbol_fixture",
        ["simple_builtin", "simple_import", "simple_func", "simple_class"],
    )
    def test_is_callable(self, symbol_fixture: str, request: pytest.FixtureRequest):
        symbol: Symbol = request.getfixturevalue(symbol_fixture)
        assert symbol.is_callable

    @pytest.mark.parametrize("symbol_fixture", ["simple_name", "simple_call"])
    def test_is_not_callable(self, symbol_fixture: str, request: pytest.FixtureRequest):
        symbol: Symbol = request.getfixturevalue(symbol_fixture)
        assert not symbol.is_callable


class TestHasLocation:
    @pytest.mark.parametrize(
        "symbol_fixture",
        ["simple_name", "simple_func", "simple_class", "simple_import", "simple_call"],
    )
    def test_has_location(
        self,
        symbol_fixture: str,
        request: pytest.FixtureRequest,
        test_file: Path,
    ):
        symbol: Symbol = request.getfixturevalue(symbol_fixture)
        assert symbol.has_location
        assert symbol.location.defined_in == test_file

    @pytest.mark.parametrize(
        "symbol_fixture",
        ["simple_builtin"],
    )
    def test_does_not_have_location(
        self,
        symbol_fixture: str,
        request: pytest.FixtureRequest,
    ):
        symbol: Symbol = request.getfixturevalue(symbol_fixture)
        assert not symbol.has_location


class TestIsImport:
    @pytest.mark.parametrize("symbol_fixture", ["simple_import"])
    def test_is_import(self, symbol_fixture: str, request: pytest.FixtureRequest):
        symbol: Symbol = request.getfixturevalue(symbol_fixture)
        assert symbol.is_import

    @pytest.mark.parametrize(
        "symbol_fixture",
        ["simple_name", "simple_builtin", "simple_func", "simple_class", "simple_call"],
    )
    def test_is_not_import(self, symbol_fixture: str, request: pytest.FixtureRequest):
        symbol: Symbol = request.getfixturevalue(symbol_fixture)
        assert not symbol.is_import


class TestDerivedConstants:
    def test_python_builtins_is_populated(self):
        assert PYTHON_BUILTINS


class TestName:
    def test_default_basename(self):
        assert Name("my_name") == Name("my_name", "my_name")

    def test_derived_basename_is_base(self):
        name, basename = "*my.complex.attr_access[]", "my"
        assert Name(name).basename == "my"
        assert Name(name) == Name(name, basename)


class TestBuiltin:
    @pytest.mark.parametrize("name", PYTHON_ATTR_ACCESS_BUILTINS)
    def test_has_affect(self, name: str):
        assert Builtin(name).has_affect

    @pytest.mark.parametrize(
        "name", (b for b in PYTHON_BUILTINS if b not in PYTHON_ATTR_ACCESS_BUILTINS)
    )
    def test_does_not_have_affect(self, name: str):
        assert not Builtin(name).has_affect


class TestImport:
    def test_non_existant(self):
        b_func = Import("func", "b.func")

        assert b_func.name == "func"
        assert b_func.qualified_name == "b.func"

        assert b_func.module_name is None
        assert b_func.module_spec is None

    @pytest.mark.parametrize(
        "name,qualified_name,module_name",
        [
            ("math", "math", "math"),
            ("pi", "math.pi", "math"),
            ("join", "os.path.join", "os.path"),
        ],
    )
    def test_qualified_name(self, name, qualified_name, module_name):
        # NOTE
        # Use `find_spec` not `find_module_spec_fast` here as we are indirectly testing
        # the correctness of the latter's impl.
        stdlib_spec = find_spec(module_name)
        rattr_spec = (
            ModuleSpec(
                name=stdlib_spec.name,
                origin=format_origin_for_os(stdlib_spec.origin),
            )
            if stdlib_spec is not None
            else None
        )

        import_ = Import(name, qualified_name)

        assert import_.name == name
        assert import_.qualified_name == qualified_name

        assert import_.module_name == module_name
        assert import_.module_spec == rattr_spec


class TestFunc:
    def test_name_excludes_call_brackets(self):
        fn = "my_lib.func"

        without_call_brackets = Func(fn, interface=AnyCallInterface())
        with_call_brackets = Func(f"{fn}()", interface=AnyCallInterface())

        assert without_call_brackets == with_call_brackets
        assert without_call_brackets.name == with_call_brackets.name == fn

    def test_from_fn_def(self):
        fn = ast.parse("def fn(a, /, b=None, *, c=False): pass").body[0]
        async_fn = ast.parse("async def fn(a, /, b=None, *, c=False): pass").body[0]

        fn_spec = {
            "name": "fn",
            "interface": CallInterface(
                posonlyargs=["a"],
                args=["b"],
                kwonlyargs=["c"],
            ),
        }
        expected = Func(**fn_spec, token=fn)
        expected_async = Func(**fn_spec, token=async_fn, is_async=True)

        assert Func.from_fn_def(fn) == expected
        assert Func.from_fn_def(async_fn) == expected_async

    def test_from_fn_def_with_vararg_and_kwarg(self):
        fn = ast.parse("def fn(a, /, b=None, *c, d=False, e=1, **f): pass").body[0]

        fn_spec = {
            "name": "fn",
            "interface": CallInterface(
                posonlyargs=["a"],
                args=["b"],
                vararg="c",
                kwonlyargs=["d", "e"],
                kwarg="f",
            ),
            "token": fn,
        }
        expected = Func(**fn_spec)

        assert Func.from_fn_def(fn) == expected


class TestClass:
    def test_name_excludes_call_brackets(self):
        cls = "my_lib.MyClass"

        without_call_brackets = Class(cls, interface=AnyCallInterface())
        with_call_brackets = Class(f"{cls}()", interface=AnyCallInterface())

        assert without_call_brackets == with_call_brackets
        assert without_call_brackets.name == with_call_brackets.name == cls

    def test_with_init(self):
        cls = Class("MyClass")
        init = ast.parse("def __init__(self, a, *, b=None): pass").body[0]

        expected = Class(
            "MyClass",
            interface=CallInterface(
                posonlyargs=[],
                args=["self", "a"],
                kwonlyargs=["b"],
            ),
        )

        assert cls.with_init(init) == expected


class TestCall:
    def test_name_excludes_call_brackets(self):
        fn = "my_lib.func"

        without_call_brackets = Call(fn, args=CallArguments())
        with_call_brackets = Call(f"{fn}()", args=CallArguments())

        assert without_call_brackets == with_call_brackets
        assert without_call_brackets.name == with_call_brackets.name == fn

    def test_from_call(self, constant):
        call = ast.parse("fn(a, b, c=var, d='yes')").body[0].value

        expected = Call(
            name="fn",
            args=CallArguments(
                args=["a", "b"],
                kwargs={"c": "var", "d": constant},
            ),
            target=None,
            token=call,
        )

        assert Call.from_call("fn", call, target=None) == expected
