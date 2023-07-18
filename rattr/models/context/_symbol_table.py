from __future__ import annotations

from typing import TYPE_CHECKING, MutableMapping

import attrs

from rattr.models.symbol import Symbol

if TYPE_CHECKING:
    from typing import Iterable, Iterator, KeysView, ValuesView


@attrs.mutable
class SymbolTable(MutableMapping[str, Symbol]):
    _symbols: dict[str, Symbol] = {}

    @property
    def names(self) -> KeysView[str]:
        return self._symbols.keys()

    @property
    def symbols(self) -> ValuesView[Symbol]:
        return self._symbols.values()

    def add(self, symbol_or_symbols: Symbol | Iterable[Symbol]) -> None:
        """Add the given symbol(s) to the symbol table."""
        if isinstance(symbol_or_symbols, Symbol):
            symbols = [symbol_or_symbols]
        else:
            symbols = symbol_or_symbols

        for symbol in symbols:
            self[symbol.id] = symbol

    def remove(self, target_or_targets: str | Symbol | list[str | Symbol]) -> None:
        """Remove the given target(s) from the symbol table."""
        if isinstance(target_or_targets, (str, Symbol)):
            targets = [target_or_targets]
        else:
            targets = target_or_targets

        for t in targets:
            del self[t if isinstance(t, str) else t.id]

    def pop(self, target: str | Symbol) -> Symbol | None:
        """Return and remove the given target, returns `None` if absent."""
        id = target.id if isinstance(target, Symbol) else target

        if id not in self:
            return

        symbol = self[id]
        del self[id]
        return symbol

    # ================================================================================ #
    # Mutable mapping abstract methods and mixin-overrides
    # ================================================================================ #

    def __getitem__(self, __key: str) -> Symbol:
        return self._symbols.__getitem__(__key)

    def __setitem__(self, __key: str, __value: Symbol) -> None:
        return self._symbols.__setitem__(__key, __value)

    def __delitem__(self, __key: str) -> None:
        return self._symbols.__delitem__(__key)

    def __iter__(self) -> Iterator[str]:
        return self._symbols.__iter__()

    def __len__(self) -> int:
        return self._symbols.__len__()

    def clear(self) -> None:
        # Faster than MutableMapping's default clear implementation
        return self._symbols.clear()
