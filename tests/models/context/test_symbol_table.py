from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import pytest

from rattr.models.context import SymbolTable
from rattr.models.symbol import CallInterface, Func, Name

if TYPE_CHECKING:
    from tests.shared import MakeSymbolTableFn


@pytest.fixture
def symbol_table(make_symbol_table: MakeSymbolTableFn) -> SymbolTable:
    return make_symbol_table(
        {
            "var": Name("var"),
            "x": Name("x"),
            "y": Name("y"),
            "z": Name("z"),
            "my_func": Func("my_func", interface=CallInterface(args=["arg"])),
        }
    )


class TestSymbolTable:
    def test_names(self, symbol_table: SymbolTable):
        assert symbol_table.names == {"var", "x", "y", "z", "my_func"}

    def test_symbols(self, symbol_table: SymbolTable):
        assert list(symbol_table.symbols) == [
            Name("var"),
            Name("x"),
            Name("y"),
            Name("z"),
            Func("my_func", interface=CallInterface(args=["arg"])),
        ]

    def test_get(self, symbol_table: SymbolTable):
        assert symbol_table.get("x") == Name("x")

    def test_get_absent(self, symbol_table: SymbolTable):
        assert symbol_table.get("nope") is None
        assert symbol_table.get("nope", None) is None


class TestSymbolTableAdd:
    def test_add(self):
        symbol_table = SymbolTable()
        symbol = Name("new_symbol")
        assert symbol not in symbol_table

        symbol_table.add(symbol)
        assert symbol.id in symbol_table
        assert list(symbol_table.symbols) == [symbol]

    def test_add_multiple(self):
        symbol_table = SymbolTable()
        symbols = [Name("new_symbol"), Name("AnotherNewSymbol")]

        for symbol in symbols:
            assert symbol not in symbol_table

        symbol_table.add(symbols)

        for symbol in symbols:
            assert symbol.id in symbol_table

        assert list(symbol_table.symbols) == symbols

    def test_add_duplicate(self, symbol_table: SymbolTable):
        before = copy.deepcopy(symbol_table)
        after = copy.deepcopy(symbol_table)

        after.add(Name("x"))
        assert before == after


class TestSymbolTableRemove:
    def test_remove_by_id(self, symbol_table: SymbolTable):
        id = "x"
        assert id in symbol_table

        symbol_table.remove(id)
        assert id not in symbol_table

    def test_remove_by_symbol(self, symbol_table: SymbolTable):
        symbol = symbol_table["x"]
        assert symbol.id in symbol_table
        assert symbol in symbol_table.symbols

        symbol_table.remove(symbol)
        assert symbol.id not in symbol_table
        assert symbol not in symbol_table.symbols

    def test_remove_multiple(self, symbol_table: SymbolTable):
        ids = ["x", "y", "z"]

        for id in ids:
            assert id in symbol_table

        symbol_table.remove(ids)

        for id in ids:
            assert id not in symbol_table

    def test_remove_missing(self, symbol_table: SymbolTable):
        before = copy.deepcopy(symbol_table)
        after = copy.deepcopy(symbol_table)

        with pytest.raises(KeyError):
            after.remove("not_a_real_symbol")
        assert before == after


class TestSymbolTablePop:
    def test_pop_by_id(self, symbol_table: SymbolTable):
        id = "x"
        assert id in symbol_table

        symbol = symbol_table.pop(id)
        assert symbol.id == id
        assert id not in symbol_table

    def test_pop_by_symbol(self, symbol_table: SymbolTable):
        symbol = Name("x")
        assert symbol in symbol_table.symbols

        symbol_ = symbol_table.pop(symbol)
        assert symbol == symbol_
        assert symbol not in symbol_table.symbols

    def test_pop_missing(self, symbol_table: SymbolTable):
        before = copy.deepcopy(symbol_table)
        after = copy.deepcopy(symbol_table)

        symbol = after.pop("not_a_real_symbol")
        assert symbol is None
        assert before == after
