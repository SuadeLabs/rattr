from __future__ import annotations

import ast
from itertools import product
from typing import TYPE_CHECKING, Final

import pytest

from rattr.ast.types import AstLiterals
from rattr.models.context._util import (
    is_call_to_call_result,
    is_call_to_literal,
    is_call_to_member_of_module_import,
    is_call_to_method,
    is_call_to_method_on_primitive_from_call,
    is_call_to_method_on_py_type,
    is_call_to_subscript_item,
    is_direct_call_to_method_on_constant,
    is_direct_call_to_method_on_literal,
)
from rattr.models.symbol._symbol import Symbol

if TYPE_CHECKING:
    from rattr.models.symbol import Import

symbol_fixtures: Final = (
    "simple_name",
    "simple_builtin",
    "simple_import",
    "simple_func",
    "simple_class",
    "simple_call",
)


class TestIsCallToLiteral:
    def test_literal(self, constant):
        assert is_call_to_literal(constant)

    @pytest.mark.parametrize("fn", ["some_function"])
    def test_non_literal(self, fn):
        assert not is_call_to_literal(fn)
        assert not is_call_to_literal(f"{fn}()")


class TestIsCallToSubscriptItem:
    def test_literal(self, constant):
        assert not is_call_to_subscript_item(constant)

    @pytest.mark.parametrize("fn", ["some_function"])
    def test_non_literal(self, fn):
        assert not is_call_to_subscript_item(fn)
        assert not is_call_to_subscript_item(f"{fn}()")

    def test_constant_subscript_element(self, constant):
        assert is_call_to_subscript_item(f"{constant}[]")
        assert is_call_to_subscript_item(f"{constant}[]()")

    def test_constant_subscript_element_method(self, constant):
        assert is_call_to_subscript_item(f"{constant}[].method")
        assert is_call_to_subscript_item(f"{constant}[].method()")

    def test_literal_subscript_element(self, literal):
        assert is_call_to_subscript_item(f"{literal(ast.List)}[]")
        assert is_call_to_subscript_item(f"{literal(ast.List)}[]()")

    def test_literal_subscript_element_method(self, literal):
        assert is_call_to_subscript_item(f"{literal(ast.List)}[].method")
        assert is_call_to_subscript_item(f"{literal(ast.List)}[].method()")

    @pytest.mark.parametrize("fn", ["my_variable[]"])
    def test_to_variable_subscript_element(self, fn):
        assert is_call_to_subscript_item(f"{fn}")
        assert is_call_to_subscript_item(f"{fn}()")

    @pytest.mark.parametrize("fn", ["my_variable[].method"])
    def test_to_variable_subscript_element_method(self, fn):
        assert is_call_to_subscript_item(f"{fn}")
        assert is_call_to_subscript_item(f"{fn}()")


class TestIsCallToMethod:
    def test_null_call_positive(self):
        assert is_call_to_method(None, "nothing", None, "nothing.method()")

    def test_null_call_negative(self):
        assert not is_call_to_method(None, "nothing", None, "nothing")

    @pytest.mark.parametrize(
        "symbol_fixture",
        [s for s in symbol_fixtures if s != "simple_import"],
    )
    def test_null_call_with_valid_lhs(
        self,
        request: pytest.FixtureRequest,
        symbol_fixture: str,
    ):
        # I.e. target was `my_variable.method()`
        # S.t. symbol = context.get("my_variable.method()") i.e. None
        # &    lsh_symbol = context.get("my_variable") i.e. from fixture
        # Excludes the case of an import, as that is not a method call!
        lhs_symbol: Symbol = request.getfixturevalue(symbol_fixture)

        assert is_call_to_method(
            None,
            f"{lhs_symbol.name}.method()",
            lhs_symbol,
            lhs_symbol.name,
        )

    def test_null_call_with_import_lhs(self, simple_import: Import):
        assert not is_call_to_method(None, "jimmy", simple_import, simple_import.name)

    @pytest.mark.parametrize(
        "symbol_fixture,lhs_symbol_fixture",
        [pair for pair in product(symbol_fixtures, symbol_fixtures)],
    )
    def test_valid_target(
        self,
        request: pytest.FixtureRequest,
        symbol_fixture: str,
        lhs_symbol_fixture: str,
    ):
        symbol: Symbol = request.getfixturevalue(symbol_fixture)
        lhs_symbol: Symbol = request.getfixturevalue(lhs_symbol_fixture)
        assert not is_call_to_method(symbol, symbol.name, lhs_symbol, lhs_symbol.name)


class TestIsCallToMemberOfModuleImport:
    @pytest.mark.parametrize("symbol_fixture", symbol_fixtures)
    def test_non_null_target(
        self,
        request: pytest.FixtureRequest,
        symbol_fixture: str,
    ):
        symbol: Symbol = request.getfixturevalue(symbol_fixture)

        assert not is_call_to_member_of_module_import("pi", symbol)
        assert not is_call_to_member_of_module_import("math.pi", symbol)

    def test_null_target(self):
        assert not is_call_to_member_of_module_import("pi", None)
        assert is_call_to_member_of_module_import("math.pi", None)


class TestIsDirectCallToMethodOnConstant:
    def test_call_to_method_on_constant(self, constant):
        assert not is_direct_call_to_method_on_constant(constant)
        assert is_direct_call_to_method_on_constant(f"{constant}.method()")

    @pytest.mark.parametrize("literal_type", AstLiterals)
    def test_call_to_method_on_literal(self, literal, literal_type):
        as_str = literal(literal_type)
        assert not is_direct_call_to_method_on_constant(as_str)
        assert not is_direct_call_to_method_on_constant(f"{as_str}.method()")

    @pytest.mark.parametrize("name", ["@Constant.pop()"])
    def test_direct_call_to_method_on_constant(self, name):
        assert is_direct_call_to_method_on_constant(name)

    @pytest.mark.parametrize("name", ["@Constant[].my_method()"])
    def test_indirect_call_to_method_on_constant(self, name):
        assert not is_direct_call_to_method_on_constant(name)

    @pytest.mark.parametrize("name", ["Constant.but_not_really()"])
    def test_is_not_call_to_method_on_constant(self, name):
        assert not is_direct_call_to_method_on_constant(name)


class TestIsDirectCallToMethodOnLiteral:
    def test_call_to_method_on_constant(self, constant):
        assert not is_direct_call_to_method_on_literal(constant)
        assert not is_direct_call_to_method_on_literal(f"{constant}.method()")

    @pytest.mark.parametrize("literal_type", AstLiterals)
    def test_direct_call_to_method_on_literal(self, literal, literal_type):
        as_str = literal(literal_type)
        assert not is_direct_call_to_method_on_literal(as_str)
        assert is_direct_call_to_method_on_literal(f"{as_str}.method()")

    @pytest.mark.parametrize("literal_type", AstLiterals)
    def test_indirect_call_to_method_on_literal(self, literal, literal_type):
        as_str = literal(literal_type)
        assert not is_direct_call_to_method_on_literal(f"{as_str}[].my_method()")

    @pytest.mark.parametrize("literal_type", AstLiterals)
    def test_is_not_call_to_method_on_literal(self, literal_type):
        as_str = literal_type.__name__
        assert not is_direct_call_to_method_on_literal(f"{as_str}.but_not_really()")


class TestIsCallToMethodOnPrimitiveFromCall:
    @pytest.mark.parametrize(
        "expr",
        [
            "int().to_bytes()",
            "str().split()",
            "int.to_bytes()",
            "str.split()",
        ],
    )
    def test_positive_case(self, expr):
        assert is_call_to_method_on_primitive_from_call(expr)

    @pytest.mark.parametrize(
        "expr",
        ["my_int.to_bytes()", "my_int().to_bytes()"],
    )
    def test_negative_case(self, expr):
        assert not is_call_to_method_on_primitive_from_call(expr)


class TestIsCallToMethodOnPyType:
    @pytest.mark.parametrize(
        "expr",
        [
            "@Constant.removeprefix()",
            "@List.append()",
            "float().from_hex()",
        ],
    )
    def test_positive_case(self, expr):
        assert is_call_to_method_on_py_type(expr)

    @pytest.mark.parametrize(
        "expr",
        [
            "@NotConstant.removeprefix()",
            "@NotList.append()",
            "my_float().from_hex()",
        ],
    )
    def test_negative_case(self, expr):
        assert not is_call_to_method_on_py_type(expr)


class TestIsCallToCallResult:
    @pytest.mark.parametrize("expr", ["my_var()()"])
    def test_positive_case(self, expr):
        assert is_call_to_call_result(ast.parse(expr).body[0].value)

    @pytest.mark.parametrize("expr", ["my_var().method()", "my_var[0]()"])
    def test_negative_case(self, expr):
        assert not is_call_to_call_result(ast.parse(expr).body[0].value)
