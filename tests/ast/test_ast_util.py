from __future__ import annotations

import ast

import pytest

from rattr import error
from rattr.ast.util import (
    basename_of,
    fullname_of,
    get_python_attr_access_fn_obj_attr_pair,
    is_call_to_fn,
    is_string_literal,
    names_of,
    unravel_names,
)
from rattr.models.symbol._symbols import PYTHON_ATTR_ACCESS_BUILTINS

# TODO Migrate tests from old utils functions


class TestIsCallToFn:
    @pytest.mark.parametrize("expr", ["thing = ..."])
    def test_not_a_call(self, expr):
        with pytest.raises(TypeError):
            is_call_to_fn(ast.parse(expr).body[0].value, "blah")

    @pytest.mark.parametrize(
        "expr,target",
        [
            ("fn(a, b, c)", "fn"),
            ("outer(inner(a, b, c))", "outer"),
        ],
    )
    def test_positive_case(self, expr, target):
        assert is_call_to_fn(ast.parse(expr).body[0].value, target)

    @pytest.mark.parametrize(
        "expr,target",
        [
            ("fn(a, b, c)", "not_fn"),
            ("outer(inner(a, b, c))", "inner"),
            ("outer(inner(a, b, c))", "neither_inner_nor_outer"),
            ("obj.method(a, b, c)", "different_func"),
            ("obj.method(a, b, c)", "obj"),
            ("obj.method(a, b, c)", "method"),
            ("obj.method(a, b, c)", "obj.method"),
            ("fn(a, b, c).on_result()", "not_fn"),
            ("fn(a, b, c).on_result()", "on_result"),
            ("fn(a, b, c).on_result()", "not_fn.on_result"),
            ("fn(a, b, c).on_result()", "not_fn().on_result"),
        ],
    )
    def test_negative_case(self, expr, target):
        assert not is_call_to_fn(ast.parse(expr).body[0].value, target)

    def test_nested_case(self):
        call: ast.Call = ast.parse("fn(a, b, c).on_result()").body[0].value

        assert not is_call_to_fn(call, "fn")
        assert is_call_to_fn(call.func.value, "fn")


class TestIsStringLiteral:
    @pytest.mark.parametrize("literal", ["'some_string'", "'1234'", "'True'"])
    def test_constant_positive_case(self, literal):
        assert is_string_literal(ast.parse(literal).body[0].value)

    @pytest.mark.parametrize("literal", ["some_var", "1234", "True"])
    def test_constant_negative_case(self, literal):
        assert not is_string_literal(ast.parse(literal).body[0].value)

    @pytest.mark.parametrize("expr", ["x = 5", "y = 'string'"])
    def test_negative_case(self, expr):
        assert not is_string_literal(ast.parse(expr).body[0])


class TestGetPythonAttrAccessFnObjAttrPair:
    @pytest.mark.parametrize(
        "expr,result",
        [
            ("getattr(a, 'b')", ("a", "b")),
            ("getattr(getattr(a, 'b'), 'c')", ("a.b", "c")),
            ("getattr(getattr(a.b[0], 'c'), 'd')", ("a.b[].c", "d")),
        ],
    )
    def test_docstring_examples(self, expr, result):
        assert (
            get_python_attr_access_fn_obj_attr_pair(
                "getattr", ast.parse(expr).body[0].value
            )
            == result
        )

    @pytest.mark.parametrize(
        "expr,result",
        [
            ("getattr(a, some_string_variable)", ("a", "<some_string_variable>")),
            ("getattr(getattr(a, var), 'attr')", ("a.<var>", "attr")),
        ],
    )
    def test_docstring_error_examples(self, arguments, expr, result):
        _expr = ast.parse(expr).body[0].value

        with arguments(is_strict=True):
            with pytest.raises(SystemExit):
                get_python_attr_access_fn_obj_attr_pair("getattr", _expr, warn=True)

        assert (
            get_python_attr_access_fn_obj_attr_pair("getattr", _expr, warn=True)
            == result
        )

    @pytest.mark.parametrize(
        "expr",
        [
            ("getattr(a or b, 'c')"),
            ("getattr(getattr(a1 or a2, 'b'), 'c')"),
        ],
    )
    def test_expr_is_illegal(self, expr):
        with pytest.raises(TypeError):
            get_python_attr_access_fn_obj_attr_pair(
                "getattr",
                ast.parse(expr).body[0].value,
            )

    def test_illegal_nesting(self):
        _expr = ast.parse("hasattr(getattr(obj, 'thing'), 'attr')").body[0].value

        with pytest.raises(SystemExit):
            get_python_attr_access_fn_obj_attr_pair("hasattr", _expr)

    @pytest.mark.parametrize("fn", PYTHON_ATTR_ACCESS_BUILTINS)
    def test_support_all_attr_accessors(self, fn):
        _expr = ast.parse(f"{fn}(obj, 'attr')").body[0].value
        assert get_python_attr_access_fn_obj_attr_pair(fn, _expr) == ("obj", "attr")


class TestNameOf:
    @pytest.mark.parametrize(
        "expr,basename,fullname",
        [
            ("my_variable", "my_variable", "my_variable"),
            ("my_variable.attr", "my_variable", "my_variable.attr"),
            ("my_variable[100].attr", "my_variable", "my_variable[].attr"),
            ("*my_variable[100].attr", "my_variable", "*my_variable[].attr"),
            ("(a, b)[0].attr", "@Tuple", "@Tuple[].attr"),
        ],
    )
    def test_docstring_examples(self, expr, basename, fullname):
        assert names_of(ast.parse(expr).body[0].value, safe=True) == (
            basename,
            fullname,
        )

    @pytest.mark.parametrize(
        "expr,error",
        [
            ("(a, b)[0].attr", error.RattrLiteralInNameable),
        ],
    )
    def test_docstring_error_examples(self, expr, error):
        with pytest.raises(error):
            names_of(ast.parse(expr).body[0].value, safe=False)


class TestBasenameOf:
    # See TestNameOf

    @pytest.mark.parametrize(
        "expr, basename",
        [
            ("var", "var"),
            ("var.attr", "var"),
        ],
    )
    def test_basename_od(self, expr, basename):
        assert basename_of(ast.parse(expr).body[0].value) == basename


class TestFullnameOf:
    # See TestNameOf

    @pytest.mark.parametrize(
        "expr, basename",
        [
            ("var", "var"),
            ("var.attr", "var.attr"),
        ],
    )
    def test_fullname_od(self, expr, basename):
        assert fullname_of(ast.parse(expr).body[0].value) == basename


class TestUnravelNames:
    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("a = 1", ["a"]),
            ("a.my_attr = 1", ["a"]),
            ("a, b = 1, 2", ["a", "b"]),
            ("(a, b), c = [1, 2], 3", ["a", "b", "c"]),
            ("(a, b), c, d.e = 1, 2, 3, 4", ["a", "b", "c", "d"]),
        ],
    )
    def test_unravel_via_basename(self, expr, expected):
        names = ast.parse(expr).body[0].targets[0]
        assert unravel_names(names) == expected

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("a = 1", ["a"]),
            ("a.my_attr = 1", ["a.my_attr"]),
            ("a, b = 1, 2", ["a", "b"]),
            ("(a, b), c = [1, 2], 3", ["a", "b", "c"]),
            ("(a, b), c, d.e = 1, 2, 3, 4", ["a", "b", "c", "d.e"]),
        ],
    )
    def test_unravel_via_fullname(self, expr, expected):
        names = ast.parse(expr).body[0].targets[0]
        assert unravel_names(names, _get_name=fullname_of) == expected
