"""Rattr symbol table."""

from typing import KeysView, ValuesView

from rattr.analyser.context.symbol import Import, Symbol


class SymbolTable(dict):
    """A map from names to symbols w.r.t. some context."""

    def add(self, symbol: Symbol) -> None:
        """Add `symbol.name -> symbol` to the symbol table."""
        name = symbol.name

        # NOTE Prevent name clash with multiple starred imports
        if isinstance(symbol, Import) and symbol.name == "*":
            name = f"{symbol.qualified_name}.*"

        self[name] = symbol

    def remove(self, name: str) -> None:
        """Remove the symbol with the given name, it it exists."""
        if name not in self.names():
            return

        del self[name]

    def names(self) -> KeysView[str]:
        """Return an iterator over the symbol table names."""
        return super().keys()

    def symbols(self) -> ValuesView[Symbol]:
        """Return an iterator over the symbol table symbols."""
        return super().values()
