from rattr.analyser.context import Name, SymbolTable


class TestSymbolTable:
    def test_add(self):
        symbol_table = SymbolTable()

        symbols = [Name("a"), Name("b")]

        for symbol in symbols:
            symbol_table.add(symbol)

        assert list(symbol_table.names()) == [s.name for s in symbols]
        assert list(symbol_table.symbols()) == symbols

    def test_remove(self):
        # Remove when absent
        symbol_table = SymbolTable()
        symbol_table.remove("a")
        assert list(symbol_table.names()) == list()

        # Remove when present
        symbol_table = SymbolTable()

        symbol_table.add(Name("a"))
        symbol_table.add(Name("b"))
        assert list(symbol_table.names()) == ["a", "b"]

        symbol_table.remove("b")
        assert list(symbol_table.names()) == ["a"]

    def test_get(self):
        symbol_table = SymbolTable()

        symbol = Name("a")
        symbol_table.add(symbol)

        assert symbol_table.get("a") is symbol
