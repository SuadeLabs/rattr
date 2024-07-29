from __future__ import annotations

import ast
from collections.abc import MutableMapping
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Union

import attrs
from attrs import field

from rattr import error
from rattr.ast.types import Identifier
from rattr.ast.util import unravel_names
from rattr.config.state import enter_file
from rattr.config.util import get_current_file
from rattr.models.context._symbol_table import SymbolTable
from rattr.models.context._util import (
    is_call_to_call_result,
    is_call_to_literal,
    is_call_to_member_of_module_import,
    is_call_to_method,
    is_call_to_method_on_imported_member,
    is_call_to_method_on_py_type,
    is_call_to_subscript_item,
)
from rattr.models.symbol._symbol import AnyCallInterface, CallInterface, Symbol
from rattr.models.symbol._symbols import Class, Func, Import, Name
from rattr.models.symbol.util import (
    with_call_brackets,
    without_call_brackets,
)
from rattr.module_locator.util import (
    derive_module_name_from_path,
    derive_module_names_right,
    module_exists,
)

if TYPE_CHECKING:
    from collections.abc import Container, Iterable, Iterator
    from typing import Protocol, TypeVar

    from rattr.models.symbol._types import CallableSymbol

    class ContainerWithContext(Protocol):
        context: Context

    SymbolType = TypeVar("SymbolType", bound=Symbol)


@contextmanager
def new_context(container: ContainerWithContext) -> Iterator[None]:
    """Set the container context to a new child in the context block, pop on exit."""
    parent = container.context
    container.context = Context(parent)
    yield
    container.context = parent


@attrs.mutable
class Context(MutableMapping[Identifier, Symbol]):
    parent: Union[Context, None]
    symbol_table: SymbolTable = field(factory=SymbolTable, kw_only=True)

    _file: Path = field(
        alias="file",
        factory=get_current_file,
        kw_only=True,
        hash=False,
        eq=False,
    )

    @property
    def file(self) -> Path:
        return self._file

    @property
    def root(self) -> Context:
        if self.parent is None:
            return self

        return self.parent.root

    @property
    def is_init_file(self) -> bool:
        return self.file.name == "__init__.py"

    @property
    def modulename(self) -> str:
        return derive_module_name_from_path(self.file)

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
    def declared_names(self) -> set[Identifier]:
        return set(self.symbol_table.names)

    @property
    def all_names(self) -> set[Identifier]:
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

        for symbol in (s for s in symbols if s.name not in self or is_argument):
            self[symbol.name] = symbol

    def remove(self, id_or_ids: Identifier | Iterable[Identifier]) -> None:
        """Remove the given id(s) from the context.

        If the symbol is declared in this context it will be removed, likewise if it is
        declared in a ancestor it will also be removed.
        """
        if isinstance(id_or_ids, Identifier):
            ids = [id_or_ids]
        else:
            ids = id_or_ids

        for id in ids:
            self.symbol_table.pop(id)

    def delete(self, id_or_ids: Identifier | Iterable[Identifier]) -> None:
        """Alias to remove."""
        self.remove(id_or_ids)

    def get_call_target(
        self,
        callee: Identifier,
        culprit: ast.AST,
        *,
        warn: bool = True,
    ) -> CallableSymbol | None:
        """Return the target of the given call as resolved within this context.

        Args:
            callee (Identifier): The callee name.
            culprit (ast.Call | ast.FunctionDef): \
                The ast.Call node, used as the error culprit. This can be an \
                ast.FunctionDef if it comes from a `rattr_results` decorator for \
                example.
            warn (bool, optional): If `True` give warnings. Defaults to True.

        Returns:
            CallableSymbol | None: The callable symbol.
        """
        canonical = with_call_brackets(callee)
        _error = f"unable to resolve call to {canonical!r}, {{reason}}"

        name = without_call_brackets(callee).replace("*", "")
        (lhs_name, *_) = name.split(".")

        if is_call_to_literal(name):
            if warn:
                error.info(
                    _error.format(reason="target lhs is a literal"),
                    culprit=culprit,
                )
            return None

        if is_call_to_subscript_item(name):
            if warn:
                if "." in name:
                    error.info(
                        _error.format(reason="target lhs is run-time dependent"),
                        culprit=culprit,
                    )
                else:
                    error.error(
                        _error.format(reason="target is run-time dependent"),
                        culprit=culprit,
                    )
            return None

        target = self.get(name)
        lhs_target = self.get(lhs_name)

        if is_call_to_method(target, name, lhs_target, lhs_name):
            if warn and not is_call_to_method_on_py_type(name):
                error.info(
                    _error.format(reason="target is a method"),
                    culprit=culprit,
                )
            return target

        # Check for calls to members of imported modules, i.e. the second case below:
        #   `from math import pi`   ->  pi is in context, already resolved above
        #   `import math`           ->  `math.pi` is not explicitly in context
        if is_call_to_member_of_module_import(name, target):
            target = self._get_target_in_imported_module(name)

        _target_is_callable = target is not None and target.is_callable

        # Give warnings for unresolvable targets
        if target is None:
            if is_call_to_method_on_imported_member(target, name, lhs_target, lhs_name):
                return None
            if warn:
                error.warning(
                    _error.format(reason="target is undefined"),
                    culprit=culprit,
                )
            return None

        if is_call_to_call_result(culprit):
            if warn:
                error.error(
                    _error.format(reason="target is a call on a call"),
                    culprit=culprit,
                )
            return target

        # Give warnings for targets likely to be resolved incorrectly
        # TODO On method support, upgrade info to warning
        if not _target_is_callable:
            if warn:
                if target is not None:
                    if "." not in name and self.declares(target.name):
                        error.error(
                            _error.format(
                                reason="target is likely a procedural parameter",
                            ),
                            culprit=culprit,
                        )
                    elif "." in target.name:
                        error.info(
                            _error.format(reason="target is a method"),
                            culprit=culprit,
                        )
                    else:
                        error.error(
                            _error.format(reason="target is not callable"),
                            culprit=culprit,
                        )
                else:
                    error.error(
                        _error.format(reason="target is not callable"),
                        culprit=culprit,
                    )
            return target

        return target

    # TODO Note to self: I don't like this method name, change it!
    def declares(self, id: Identifier) -> bool:
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

    def add_identifiers_to_context(self, assignment: ast.expr) -> None:
        self.add(Name(name, token=assignment) for name in unravel_names(assignment))

    def remove_identifiers_from_context(self, assignment: ast.expr) -> None:
        self.remove(unravel_names(assignment))

    def add_arguments_to_context(
        self,
        arguments: ast.arguments,
        *,
        token: ast.AST,
    ) -> None:
        self.add(
            Name(arg, token=token)
            for arg in CallInterface.from_arguments(arguments).all
        )

    # ================================================================================ #
    # Syntactic sugar methods
    # ================================================================================ #

    def expand_starred_imports(self) -> Context:
        """Recursively follow starred imports and add the discovered names to the scope.

        This is an in-place operation which returns self.
        """
        from rattr.models.context._root_context import compile_root_context

        seen: set[Path] = set()
        queue = self.get_starred_imports(seen_by_origin=seen)

        # BFS the unseen starred imports
        for starred in queue:
            if starred.origin is None:
                error.error(
                    f"unable to resolve import {starred.name!r} while expanding "
                    f"{starred.code()!r}",
                    culprit=starred,
                )
                continue

            if starred.origin in seen:
                continue

            # Visit node
            with enter_file(starred.origin):
                starred_ast = ast.parse(starred.origin.read_text())
                starred_context = compile_root_context(starred_ast)

            # Progress breadth-first search queue
            seen.add(starred.origin)
            queue += starred_context.get_starred_imports(seen_by_origin=seen)

            # Add the resolved names to this context
            for symbol in starred_context.declared_symbols:
                self.add(
                    Import(
                        name=symbol.name,
                        qualified_name=f"{starred.qualified_name}.{symbol.name}",
                        location=starred.location,
                        interface=symbol.interface,
                    )
                )

        return self

    def get_class_or_error(self, name: Identifier) -> Class:
        cls = self.get(name)

        if cls is None or not isinstance(cls, Class):
            raise KeyError(f"class {name!r} is not defined in the current context")

        return cls

    def get_func_or_error(self, name: Identifier) -> Func:
        func = self.get(name)

        if func is None or not isinstance(func, Func):
            raise KeyError(f"function {name!r} is not defined in the current context")

        return func

    # ================================================================================ #
    # Private helper methods
    # ================================================================================ #

    def _get_target_in_imported_module(self, name: Identifier) -> Symbol | None:
        modules = [self.get(m) for m in derive_module_names_right(name)]
        module = next((m for m in modules if m is not None), None)

        if not isinstance(module, Import):
            return None

        # We saw `import bar`/`from foo import bar` and then `bar.thing`
        # If `bar` is a module we want to construct the indirect import but if it is not
        # a module then bar must be a class/function/variable/constant.
        if not module_exists(module.qualified_name):
            return None

        return Import(
            name=(local_name := name.replace(f"{module.name}.", "")),
            qualified_name=f"{module.qualified_name}.{local_name}",
            location=module.location,
            interface=AnyCallInterface(),
        )

    # ================================================================================ #
    # Mutable mapping abstract methods and mixin-overrides
    # ================================================================================ #

    def __getitem__(self, __key: Identifier) -> Symbol:
        if __key in self.symbol_table:
            return self.symbol_table.__getitem__(__key)

        if self.parent is None:
            raise KeyError(__key)

        return self.parent.__getitem__(__key)

    def __setitem__(self, __key: Identifier, __value: Symbol) -> None:
        _error = f"symbol key and id do not match: {__key!r} != {__value.id!r}"

        if __key == "*" and not __value.id.endswith(".*"):
            raise ValueError(_error)

        if __key != "*" and __key != __value.id:
            raise ValueError(_error)

        return self.symbol_table.add(__value)

    def __delitem__(self, __key: Identifier) -> None:
        if __key in self.symbol_table:
            return self.symbol_table.__delitem__(__key)

        if self.parent is None:
            raise KeyError(__key)

        return self.parent.__delitem__(__key)

    def __iter__(self) -> Iterator[Identifier]:
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
