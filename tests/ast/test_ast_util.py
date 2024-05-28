from __future__ import annotations

import ast
import re

import pytest

from rattr import error
from rattr.ast.util import (
    NAMEDTUPLE_INVALID_SECOND_PARAMETER_VALUE_ERROR,
    NAMEDTUPLE_INVALID_SIGNATURE_ERROR,
    assignment_is_one_to_one,
    assignment_targets,
    basename_of,
    fullname_of,
    get_python_attr_access_fn_obj_attr_pair,
    has_lambda_in_rhs,
    has_namedtuple_declaration_in_rhs,
    has_walrus_in_rhs,
    is_call_to_fn,
    is_relative_import,
    is_starred_import,
    is_string_literal,
    namedtuple_init_signature_from_declaration,
    names_of,
    parse_space_delimited_ast_string,
    unpack_ast_list_of_strings,
    unravel_names,
    walruses_in_rhs,
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


class TestIsStarredImport:
    @pytest.mark.parametrize(
        "stmt",
        [
            "from math import *",
            "from .relative.module import *",
        ],
    )
    def test_is_starred_import(self, stmt):
        assert is_starred_import(ast.parse(stmt).body[0])

    @pytest.mark.parametrize(
        "stmt",
        [
            "import math",
            "from math import pi",
            "from math import sin, cos, tan",
        ],
    )
    def test_is_not_starred_import(self, stmt):
        assert not is_starred_import(ast.parse(stmt).body[0])


class TestIsRelativeImport:
    @pytest.mark.parametrize(
        "stmt",
        [
            "from .relative.module import my_util",
            "from .relative.module import MyClass, my_util, my_other_util",
            "from .relative.module import *",
        ],
    )
    def test_is_relative_import(self, stmt):
        assert is_relative_import(ast.parse(stmt).body[0])

    @pytest.mark.parametrize(
        "stmt",
        [
            "import math",
            "from math import pi",
            "from math import sin, cos, tan",
            "from math import *",
        ],
    )
    def test_is_not_relative_import(self, stmt):
        assert not is_relative_import(ast.parse(stmt).body[0])


@pytest.mark.parametrize(
    "expr, expected",
    testcases := [
        ("a = 1", ["a"]),
        ("a, b = 1, 2", ["a", "b"]),
        ("a: int = 1", ["a"]),
        ("a += 1", ["a"]),
    ],
    ids=[t[0] for t in testcases],
)
def test_assignment_targets(expr: str, expected: list[ast.expr]):
    # We must convert to str and compare as `ast.Name(id="a") != ast.Name(id="a")` as
    # ast node equality is an `is` check.
    targets = [
        name
        for target in assignment_targets(ast.parse(expr).body[0])
        for name in unravel_names(target)
    ]
    assert targets == expected


def test_assignment_targets_in_walrus():
    parsed = ast.parse("a = (b := 1)")

    a: ast.Assign = parsed.body[0]
    b: ast.NamedExpr = parsed.body[0].value

    assert assignment_targets(a) == a.targets
    assert assignment_targets(b) == [b.target]


@pytest.mark.parametrize(
    "expr, expected",
    testcases := [
        ("x = 1", True),
        ("x: int = 1", True),
        ("x += 1", True),
        ("x, y = z", False),
        ("x, y = a, b", False),
        ("x = y, z", False),
        ("x += y, z", False),
    ],
    ids=[t[0] for t in testcases],
)
def test_assignment_is_one_to_one(expr: str, expected: bool):
    assert assignment_is_one_to_one(ast.parse(expr).body[0]) == expected


@pytest.mark.parametrize(
    "expr, expected",
    testcases := [
        ("a = lambda: 1", True),
        ("a = 1, lambda: 1", True),
        ("a: SomeType = lambda: 1", True),
        ("a += lambda: 1", True),
        ("a = 1", False),
        ("a = 1, 2", False),
        ("a: SomeType = SomeType()", False),
        ("a += 1", False),
    ],
    ids=[t[0] for t in testcases],
)
def test_has_lambda_in_rhs(expr: str, expected: bool):
    assert has_lambda_in_rhs(ast.parse(expr).body[0]) == expected


@pytest.mark.parametrize(
    "expr, expected",
    testcases := [
        ("a = (b := c)", True),
        ("a = 1, (b := c)", True),
        ("a: SomeType = (b := c)", True),
        ("a += (b := c)", True),
        ("a = 1", False),
        ("a = 1, 2", False),
        ("a: SomeType = SomeType()", False),
        ("a += 1", False),
    ],
    ids=[t[0] for t in testcases],
)
def test_has_walrus_in_rhs(expr: str, expected: bool):
    assert has_walrus_in_rhs(ast.parse(expr).body[0]) == expected


@pytest.mark.parametrize(
    "expr, expected",
    testcases := [
        ("a = b", []),
        ("a = (b := c)", ["b := c"]),
        ("a = (x := y, m := n)", ["x := y", "m := n"]),
        ("a = (b, x := y)", ["x := y"]),
        ("a = (b, (c, x := y))", []),  # we don't handle nested walruses
    ],
    ids=[t[0] for t in testcases],
)
def test_walruses_in_rhs(walrus, expr: str, expected: list[str]):
    # We stringify the nodes here as the lhs and rhs will be equivalent but have
    # different addresses so fail "==" (which is an "is" check for ast.NamedExpr it
    # seems)
    actual_as_string = [ast.dump(e) for e in walruses_in_rhs(ast.parse(expr).body[0])]
    expected_as_string = [ast.dump(walrus(e)) for e in expected]
    assert actual_as_string == expected_as_string


@pytest.mark.parametrize(
    "expr, expected",
    testcases := [
        ("point = namedtuple('point', ['x', 'y'])", True),
        ("point = user_extended.namedtuple('point', ['x', 'y'])", True),
        ("point = noomedtoople('point', ['x', 'y'])", False),
    ],
    ids=[t[0] for t in testcases],
)
def test_has_namedtuple_declaration_in_rhs(expr: str, expected: bool):
    assert has_namedtuple_declaration_in_rhs(ast.parse(expr).body[0]) == expected


def test_namedtuple_init_signature_from_declaration_not_a_call():
    with pytest.raises(TypeError):
        namedtuple_init_signature_from_declaration(ast.parse("'not_a_call'").body[0])


@pytest.mark.parametrize(
    "expr, error",
    testcases := [
        (
            "namedtuple('point')",
            re.escape(NAMEDTUPLE_INVALID_SIGNATURE_ERROR),
        ),
        (
            "namedtuple('point', 'x', 'y')",
            re.escape(NAMEDTUPLE_INVALID_SIGNATURE_ERROR),
        ),
        (
            "namedtuple('point', ('x', 'y'))",
            re.escape(NAMEDTUPLE_INVALID_SECOND_PARAMETER_VALUE_ERROR),
        ),
        (
            "namedtuple('point', ['x', 123])",
            re.escape(NAMEDTUPLE_INVALID_SECOND_PARAMETER_VALUE_ERROR),
        ),
        (
            "namedtuple('point', ['x', some_variable])",
            re.escape(NAMEDTUPLE_INVALID_SECOND_PARAMETER_VALUE_ERROR),
        ),
    ],
    ids=[t[0] for t in testcases],
)
def test_namedtuple_init_signature_from_declaration_invalid(expr: str, error: str):
    with pytest.raises(ValueError, match=error):
        namedtuple_init_signature_from_declaration(ast.parse(expr).body[0])


@pytest.mark.parametrize(
    "expr, attributes",
    testcases := [
        ("namedtuple('point', [])", ["self"]),
        ("namedtuple('point', ['x'])", ["self", "x"]),
        ("namedtuple('point', ['x', 'y'])", ["self", "x", "y"]),
        ("vec4('vector', ['a', 'b', 'c', 'd'])", ["self", "a", "b", "c", "d"]),
    ],
    ids=[t[0] for t in testcases],
)
def test_namedtuple_init_signature_from_declaration(expr: str, attributes: list[str]):
    assert (
        namedtuple_init_signature_from_declaration(ast.parse(expr).body[0])
        == attributes
    )


@pytest.mark.parametrize(
    "expr, expected",
    testcases := [
        ("[]", []),
        ("['a', 'b', 'c']", ["a", "b", "c"]),
    ],
    ids=[t[0] for t in testcases],
)
def test_unpack_ast_list_of_strings(expr: str, expected: list[str]):
    assert unpack_ast_list_of_strings(ast.parse(expr).body[0].value) == expected


def test_unpack_ast_list_of_strings_invalid():
    with pytest.raises(SyntaxError):
        unpack_ast_list_of_strings(ast.parse("[not_a_string_literal]").body[0].value)


@pytest.mark.parametrize(
    "expr, expected",
    testcases := [
        ("''", []),
        ("'a b c'", ["a", "b", "c"]),
    ],
    ids=[t[0] for t in testcases],
)
def test_parse_space_delimited_ast_string(expr: str, expected: list[str]):
    assert parse_space_delimited_ast_string(ast.parse(expr).body[0].value) == expected


def test_parse_space_delimited_ast_string_invalid():
    with pytest.raises(SyntaxError):
        parse_space_delimited_ast_string(ast.parse("blah 0invalid").body[0].value)
