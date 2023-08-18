from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, MutableMapping

import attrs
from attrs import field

from rattr import error
from rattr.ast.util import unravel_names
from rattr.config.state import enter_file
from rattr.config.util import get_current_file
from rattr.models.context._symbol_table import SymbolTable
from rattr.models.context._util import (
    is_call_to_call_result,
    is_call_to_literal,
    is_call_to_member_of_module_import,
    is_call_to_method,
    is_call_to_method_on_py_type,
    is_call_to_subscript_item,
)
from rattr.models.symbol._symbol import CallInterface, Symbol
from rattr.models.symbol._symbols import Import, Name
from rattr.models.symbol.util import (
    get_possible_module_names,
    with_call_brackets,
    without_call_brackets,
)

if TYPE_CHECKING:
    import ast
    from typing import Container, Iterable, Iterator

    from rattr.ast.types import AnyAssign
    from rattr.models.symbol._types import CallableSymbol
    from rattr.versioning.typing import TypeAlias


_Identifier: TypeAlias = str


@attrs.mutable
class Context(MutableMapping[_Identifier, Symbol]):
    parent: Context | None
    symbol_table: SymbolTable = field(factory=SymbolTable, kw_only=True)
    _file: Path = field(factory=get_current_file, kw_only=True)

    @property
    def file(self) -> Path:
        return self._file

    @property
    def root(self) -> Context:
        if self.parent is None:
            return self

        return self.parent.root

    @property
    def declared_symbols(self) -> set[Symbol]:
        """The symbols declared in this scope (excl. symbols in ancestor scopes)."""
        return set(self.symbol_table.symbols)

    @property
    def all_symbols(self) -> set[Symbol]:
        """The symbols present in this scope (incl. symbols in ancestor scopes)."""
        if self.parent is None:
            return self.declared_symbols

        return self.declared_symbols | self.parent.all_symbols

    @property
    def declared_names(self) -> set[_Identifier]:
        return set(self.symbol_table.names)

    @property
    def all_names(self) -> set[_Identifier]:
        if self.parent is None:
            return self.declared_names

        return self.declared_names | self.parent.all_names

    def add(
        self,
        symbol_or_symbols: Symbol | Iterable[Symbol],
        *,
        is_argument: bool = False,
    ) -> None:
        """Add the given symbol(s) to the context.

        If the symbol is already present in the context, or an ancestor, then
        it will not be re-added.

        If the symbol `is_argument`, then the symbol will always be added
        regardless of whether-or-not it is declared in an ancestor.
        """
        if isinstance(symbol_or_symbols, Symbol):
            symbols = [symbol_or_symbols]
        else:
            symbols = symbol_or_symbols

        for symbol in (s for s in symbols if is_argument or s not in self):
            self[symbol.name] = symbol

    def remove(self, id_or_ids: _Identifier | Iterable[_Identifier]) -> None:
        """Remove the given id(s) from the context.

        If the symbol is declared in this context it will be removed, likewise if it is
        declared in a ancestor it will also be removed.
        """
        if isinstance(id_or_ids, _Identifier):
            ids = [id_or_ids]
        else:
            ids = id_or_ids

        for id in ids:
            self.pop(id)

    def delete(self, id_or_ids: _Identifier | Iterable[_Identifier]) -> None:
        """Alias to remove."""
        self.remove(id_or_ids)

    def get_call_target(
        self,
        callee: _Identifier,
        culprit: ast.Call,
        *,
        warn: bool = True,
    ) -> CallableSymbol | None:
        """Return the target of the given call as resolved within this context.

        Args:
            callee (str): The callee name.
            culprit (ast.Call): The AST call node, used as the error culprit.
            warn (bool, optional): If `True` give warnings. Defaults to True.

        Returns:
            CallableSymbol | None: The callable symbol.
        """
        canonical = with_call_brackets(callee)
        _error = f"unable to resolve call to {canonical!r}, {{reason}}"

        name = without_call_brackets(callee).replace("*", "")
        (lhs_name, *_) = name.split(".")[0]

        if is_call_to_literal(name):
            error.error(_error.format(reason="target lhs is a literal"), culprit)
            return None

        if is_call_to_subscript_item(name):
            error.error(_error.format(reason="target is run-time dependent"), culprit)
            return None

        target = self.get(name)
        lhs_target = self.get(lhs_name)

        if is_call_to_method(target, lhs_target):
            error.error(_error.format(reason="target is a method"), culprit)
            return None

        # Check for calls to members of imported modules, i.e. the second case below:
        #   `from math import pi`   ->  pi is in context, already resolved above
        #   `import math`           ->  `math.pi` is not explicitly in context
        if is_call_to_member_of_module_import(name, target):
            target = self._get_containing_module_target(name)

        _target_is_callable = target is not None and target.is_callable

        # Give warnings for unresolvable targets
        if warn and target is None:
            if not is_call_to_method_on_py_type(name):
                error.error(_error.format(reason="target is a method"), culprit)

            if is_call_to_call_result(name):
                error.error(_error.format(reason="target is a call on a call"), culprit)

        # Give warnings for targets likely to be resolved incorrectly
        # TODO On method support, upgrade info to warning
        if warn and not _target_is_callable:
            if "." not in name and self.declares(target.name):
                error.error(
                    _error.format(reason="likely a procedural parameter"), culprit
                )
            elif "." in target.name:
                error.info(_error.format(reason="target is a method"), culprit)
            else:
                error.error(_error.format(reason="target is not callable"), culprit)

        return target

    # TODO Note to self: I don't like this, change it!
    def declares(self, id: _Identifier) -> bool:
        """Return `True` if the id was defined in this context, not a parent."""
        return id in self.symbol_table

    def get_starred_imports(
        self,
        *,
        seen_by_origin: Container[Path] | None = None,
    ) -> list[Import]:
        """Return the starred imports in the current context, skipping previously seen.

        Args:
            seen (Container[str] | None, optional):
                The previously seen starred imports by the module spec's origin.
                Defaults to None.

        Returns:
            list[Import]: The starred imports.
        """
        return [
            symbol
            for symbol in self.declared_symbols
            if isinstance(symbol, Import) and symbol.name == "*"
            if symbol.origin not in seen_by_origin or ()
        ]

    # ================================================================================ #
    # Registration helpers
    # ================================================================================ #

    def add_identifiers_to_context(self, assignment: AnyAssign) -> None:
        self.add(Name(name) for name in unravel_names(assignment))

    def remove_identifiers_from_context(self, assignment: AnyAssign) -> None:
        self.remove(unravel_names(assignment))

    def add_arguments_to_context(self, arguments: ast.arguments) -> None:
        self.add(Name(arg) for arg in CallInterface.from_arguments(arguments).all)

    # ================================================================================ #
    # Syntactic sugar methods
    # ================================================================================ #

    def expand_starred_imports(self) -> Context:
        """Recursively follow starred imports and add the discovered names to the scope.

        This is an in-place operation which returns self.
        """
        seen: set[Path] = set()
        queue = self.get_starred_imports(seen_by_origin=seen)

        # BFS the unseen starred imports
        for starred in queue:
            if starred.origin is None:
                error.error(
                    f"unable to resolve import {starred.name!r} while expanding "
                    f"{starred.code!r}",
                    culprit=starred.token,
                )
                continue

            if starred.origin in seen:
                continue

            # TODO NEW ROOT CONTEXT REQUIRED
            # Visit node
            with enter_file(starred.origin):
                starred_ast = ast.parse(starred.origin.read_text())
                starred_context: Context = ...
                raise NotImplementedError(starred_ast)

            # Progress breadth-first search queue
            seen.add(starred.origin)
            queue += starred_context.get_starred_imports(seen_by_origin=seen)

            # Add the resolved names to this context
            for symbol in starred_context.declared_symbols:
                self.add(Import(symbol.name, f"{starred.qualified_name}.{symbol.name}"))

        return self

    # ================================================================================ #
    # Private helper methods
    # ================================================================================ #

    def _get_containing_module_target(self, name: _Identifier) -> Symbol | None:
        modules = [self.get(m) for m in get_possible_module_names(name)]
        module = next((m for m in modules if m is not None), None)

        if not isinstance(module, Import):
            return None

        local_name = name.replace(f"{module.name}.", "")

        return Import(
            name=local_name,
            qualified_name=f"{module.qualified_name}.{local_name}",
        )

    # ================================================================================ #
    # Mutable mapping abstract methods and mixin-overrides
    # ================================================================================ #

    def __getitem__(self, __key: _Identifier) -> Symbol:
        if __key in self.symbol_table:
            return self.symbol_table.__getitem__(__key)

        if self.parent is None:
            raise KeyError(__key)

        return self.parent.__getitem__(__key)

    def __setitem__(self, __key: _Identifier, __value: Symbol) -> None:
        if __key != __value.id:
            raise ValueError("symbol key and id do not match")

        return self.symbol_table.add(__value)

    def __delitem__(self, __key: _Identifier) -> None:
        if __key in self.symbol_table:
            return self.symbol_table.__delitem__(__key)

        if self.parent is None:
            raise KeyError(__key)

        return self.parent.__delitem__(__key)

    def __iter__(self) -> Iterator[_Identifier]:
        # Get the chain of ancestors from here to root
        contexts: list[Context] = [ctx := self]

        while (ctx := ctx.parent) is not None:
            contexts.append(ctx)

        # Yield the symbols from each context, from the root context to this context,
        # in order of declaration. As dicts are insert-ordered, and symbol tables are
        # dicts with symbols inserted in declaration order, order holds if we order the
        # contexts from root to current.
        for context in reversed(contexts):
            yield from context.symbol_table.__iter__()

    def __len__(self) -> int:
        return self.all_symbols.__len__()

    def clear(self) -> None:
        raise TypeError("a context is mutable but not re-usable")

    def update(self) -> None:
        raise TypeError("a context is mutable but not re-usable")
