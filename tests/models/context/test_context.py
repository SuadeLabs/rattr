from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from rattr.models.context import Context
from rattr.models.symbol import CallInterface, Func, Name

if TYPE_CHECKING:
    from tests.shared import ArgumentsFn, MakeSymbolTableFn, ParseFn


def test_context_add():
    root = Context(parent=None)
    child = Context(parent=root)

    root.add(symbol_in_root := Name(name="name_in_root"))
    child.add(symbol_in_child := Name(name="name_in_child"))

    assert symbol_in_root.name in root
    assert symbol_in_root.name in child

    assert symbol_in_child.name not in root
    assert symbol_in_child.name in child


def test_context_add_does_not_duplicate():
    root = Context(parent=None)
    child = Context(parent=root)

    root.add(symbol := Name(name="name"))
    child.add(symbol)

    assert symbol in root.symbol_table.symbols

    assert symbol not in child.symbol_table.symbols
    assert symbol.name in child


def test_context_add_multiple():
    root = Context(parent=None)
    symbols = (Name("first"), Name("second"), Name("third"))

    root.add(symbols)

    for symbol in symbols:
        assert symbol.name in root


def test_context_add_as_argument(make_symbol_table: MakeSymbolTableFn):
    # When added as an argument a symbol should be in both the root and child symbol
    # tables, when normally it would not be re-added.
    # See test_context_add_does_not_duplicate
    root = Context(parent=None)
    child = Context(parent=root)

    root.add(symbol := Name(name="name"))
    child.add(symbol, is_argument=True)

    expected_symbol_table = make_symbol_table({symbol.name: symbol})
    assert root.symbol_table == expected_symbol_table
    assert child.symbol_table == expected_symbol_table


def test_context_remove():
    root = Context(parent=None)

    root.add((a := Name("a"), b := Name("b")))
    assert root.symbol_table._symbols == {a.name: a, b.name: b}
    assert a.name in root

    root.remove(a.name)
    assert root.symbol_table._symbols == {b.name: b}
    assert a.name not in root


def test_context_remove_from_parent():
    root = Context(parent=None)
    root.add((a := Name("a"), b := Name("b")))

    child = Context(parent=root)

    assert root.symbol_table._symbols == {a.name: a, b.name: b}
    assert child.symbol_table._symbols == {}

    child.remove(a.name)
    assert root.symbol_table._symbols == {a.name: a, b.name: b}
    assert child.symbol_table._symbols == {}

    root.remove(a.name)
    assert root.symbol_table._symbols == {b.name: b}
    assert child.symbol_table._symbols == {}


def test_context_remove_non_existent():
    root = Context(parent=None)
    root.add((a := Name("a"), b := Name("b")))

    child = Context(parent=root)

    root.remove("fake")
    root.remove("false")

    assert root.symbol_table._symbols == {a.name: a, b.name: b}
    assert child.symbol_table._symbols == {}


def test_context_remove_all():
    root = Context(parent=None)
    root.add((a := Name("a"), b := Name("b")))

    root.remove((a.name, b.name, "fake"))
    assert root.symbol_table._symbols == {}


def test_context_get():
    root = Context(parent=None)
    root.add((a := Name("a"), b := Name("b")))

    assert root.get(a.name) == a
    assert root.get(b.name) == b
    assert root.get("fake") is None


def test_context_get_call_target_not_defined(capfd: pytest.CaptureFixture[str]):
    root = Context(parent=None)
    assert root.get_call_target("anything", culprit=None) is None

    _, stderr = capfd.readouterr()
    assert "unable to resolve call to 'anything()', target is undefined" in stderr


def test_context_get_call_target_not_callable(capfd: pytest.CaptureFixture[str]):
    root = Context(parent=None)
    root.add(a := Name("a"))
    child = Context(parent=root)

    # The root defines 'a' so it is likely a procedural parameter in practise
    assert root.get_call_target(a.name, culprit=None) == a
    _, stderr = capfd.readouterr()
    assert (
        "unable to resolve call to 'a()', target is likely a procedural parameter"
        in stderr
    )

    # The child merely inherits 'a' so it is just generically not callable
    assert child.get_call_target(a.name, culprit=None) == a
    _, stderr = capfd.readouterr()
    assert "unable to resolve call to 'a()', target is not callable" in stderr


def test_context_get_call_target_method(
    capfd: pytest.CaptureFixture[str],
    arguments: ArgumentsFn,
):
    root = Context(parent=None)
    root.add(Name("a"))

    with arguments(_warning_level="all"):
        assert root.get_call_target("a.method()", culprit=None) is None

    _, stderr = capfd.readouterr()
    assert "unable to resolve call to 'a.method()', target is a method" in stderr


def test_context_get_call_func_target(capfd: pytest.CaptureFixture[str]):
    root = Context(parent=None)
    root.add(func := Func(name="a", interface=CallInterface()))

    assert root.get_call_target("a()", culprit=None) == func


def test_context_get_call_target_brackets_dont_matter():
    root = Context(parent=None)
    root.add(a := Func(name="a", interface=CallInterface()))

    assert root.get_call_target(a.name, culprit=None) == a
    assert root.get_call_target(f"{a.name}()", culprit=None) == a


def test_context_declares():
    root = Context(parent=None)
    root.add(a := Name("a"))

    child = Context(root)
    child.add(b := Name("b"))

    assert root.declares(a.name)
    assert not child.declares(a.name)

    assert not root.declares(b.name)
    assert child.declares(b.name)


def test_context_in():
    root = Context(parent=None)
    root.add(a := Name("a"))

    child = Context(root)
    child.add(b := Name("b"))

    assert a.name in root
    assert b.name not in root

    assert a.name in child
    assert b.name in child


def test_context_add_identifiers_to_context_single():
    expr: ast.Name = ast.parse("a = 1").body[0].targets[0]

    root = Context(parent=None)
    root.add_identifiers_to_context(expr)

    assert root.symbol_table._symbols == {"a": Name("a", token=expr)}


def test_context_add_identifiers_to_context_multiple():
    expr: ast.Name = ast.parse("a, b, c = 1, 2, 3").body[0].targets[0]

    root = Context(parent=None)
    root.add_identifiers_to_context(expr)
    assert root.symbol_table._symbols == {
        "a": Name("a", token=expr),
        "b": Name("b", token=expr),
        "c": Name("c", token=expr),
    }


def test_context_remove_identifiers_from_context_single():
    expr: ast.Name = ast.parse("del a").body[0].targets[0]

    root = Context(parent=None)

    root.add(Name("a"))
    assert root.symbol_table._symbols == {"a": Name("a")}

    root.remove_identifiers_from_context(expr)
    assert root.symbol_table._symbols == {}


def test_context_remove_identifiers_from_context_multiple():
    targets: list[ast.Name] = ast.parse("del a, b").body[0].targets
    (expr_a, expr_b) = targets

    root = Context(parent=None)
    root.add(Name("a"))
    root.add(Name("b"))
    assert root.symbol_table._symbols == {"a": Name("a"), "b": Name("b")}

    root.remove_identifiers_from_context(expr_a)
    root.remove_identifiers_from_context(expr_b)
    assert root.symbol_table._symbols == {}


@pytest.mark.parametrize(
    "source_code, expected_names",
    [
        (
            """
            def fn():
                pass
            """,
            [],
        ),
        (
            """
            def fn(a, b, c=1, d=2, *x, **y):
                pass
            """,
            ["a", "b", "c", "d", "x", "y"],
        ),
    ],
)
def test_context_add_arguments_to_context(
    source_code: str,
    expected_names: list[str],
    parse: ParseFn,
    make_symbol_table: MakeSymbolTableFn,
):
    function: ast.FunctionDef = parse(source_code).body[0]

    root = Context(parent=None)
    root.add_arguments_to_context(function.args, token=None)

    assert root.symbol_table == make_symbol_table(
        [Name(name, token=function) for name in expected_names]
    )


def test_context_redefinition_in_scope():
    root = Context(parent=None)

    root.add(Name("var_one"))
    root.add(Name("var_one"))

    assert root.symbol_table._symbols == {"var_one": Name("var_one")}


def test_context_redefinition_in_child_scope():
    root = Context(parent=None)
    root.add(Name("var_one"))

    child = Context(parent=root)
    child.add(Name("var_one"))

    assert root.symbol_table._symbols == {"var_one": Name("var_one")}
    assert child.symbol_table._symbols == {}
