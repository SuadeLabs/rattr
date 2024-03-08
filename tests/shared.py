from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import attrs
from attrs import field

from rattr.models.context._root_context import (
    MODULE_LEVEL_DUNDER_ATTRS,
    PYTHON_BUILTINS,
)
from rattr.models.symbol import Import

if TYPE_CHECKING:
    import ast
    from collections.abc import Iterable, Iterator, Mapping
    from pathlib import Path
    from typing import Any, Protocol, TypeVar

    from rattr.ast.types import Identifier
    from rattr.config import Arguments, State
    from rattr.models.context import Context, SymbolTable
    from rattr.models.ir import FileIr, FunctionIr
    from rattr.models.symbol import Symbol, UserDefinedCallableSymbol
    from rattr.module_locator.models import ModuleSpec
    from rattr.module_locator.util import ModuleName

    class FileIrFromDictFn(Protocol):
        def __call__(
            self,
            ir: Mapping[UserDefinedCallableSymbol, FunctionIr],
        ) -> FileIr:
            ...

    class MakeSymbolTableFn(Protocol):
        def __call__(
            self,
            symbols: Mapping[Identifier, Symbol] | Iterable[Symbol],
            *,
            include_root_symbols: bool = False,
        ) -> SymbolTable:
            ...

    class MakeRootContextFn(Protocol):
        def __call__(
            self,
            symbols: Mapping[Identifier, Symbol] | Iterable[Symbol],
            *,
            include_root_symbols: bool = False,
        ) -> Context:
            ...

    class ArgumentsFn(Protocol):
        def __call__(
            self,
            **kwargs: Mapping[str, Any],
        ) -> Iterator[None]:
            ...

    class StateFn(Protocol):
        def __call__(
            self,
            **kwargs: Mapping[str, Any],
        ) -> Iterator[None]:
            ...

    class SetTestingConfigFn(Protocol):
        def __call__(self, arguments: Arguments, state: State = None) -> None:
            ...

    class ParseFn(Protocol):
        def __call__(self, source: str) -> ast.Module:
            ...

    class ParseWithContextFn(Protocol):
        def __call__(self, source: str) -> tuple[ast.Module, Context]:
            ...

    StrOrPath = TypeVar("StrOrPath", str, Path)

    class OsDependentPathFn(Protocol):
        def __call__(self, target: StrOrPath) -> StrOrPath:
            ...


@attrs.frozen
class Import_(Import):
    """
    This is a specialisation of `Import` where the module name and spec can be set
    explicitly, which is useful for many tests.
    """

    _module_name_and_spec: tuple[ModuleName, ModuleSpec] = field(
        alias="module_name_and_spec",
        default=("blah", "blah"),
    )


def compare_identifier_symbol_mappings(
    lhs: Mapping[Identifier, FunctionIr],
    rhs: Mapping[Identifier, FunctionIr],
    /,
) -> bool:
    errors: list[str] = []

    keys = lhs.keys()
    other_keys = rhs.keys()

    if extra := (keys - other_keys):
        errors.append(f"extra keys in lhs: {extra}")
    if extra := (other_keys - keys):
        errors.append(f"extra keys in rhs: {extra}")

    for key in keys & other_keys:
        if key in MODULE_LEVEL_DUNDER_ATTRS or key in PYTHON_BUILTINS:
            lhs_symbol = attrs.evolve(lhs[key], token=mock.ANY, location=mock.ANY)
            rhs_symbol = attrs.evolve(rhs[key], token=mock.ANY, location=mock.ANY)
        else:
            lhs_symbol = lhs[key]
            rhs_symbol = rhs[key]

        if lhs_symbol == rhs_symbol:
            continue

        errors.append(f"{lhs_symbol} != {rhs_symbol}")

    if errors:
        print("\n".join(errors))
        return False

    return True


def compare_symbol_table_symbols(
    lhs: SymbolTable,
    rhs: SymbolTable,
    /,
) -> bool:
    return compare_identifier_symbol_mappings(lhs, rhs)


def match_output(
    actual_stdout_or_stderr: str | Iterable[str],
    expected_stdout_or_stderr: str | Iterable[str],
) -> bool:
    if isinstance(actual_stdout_or_stderr, str):
        actual_lines = actual_stdout_or_stderr.splitlines()
    else:
        actual_lines = actual_stdout_or_stderr

    if isinstance(expected_stdout_or_stderr, str):
        expected_lines = expected_stdout_or_stderr.splitlines()
    else:
        expected_lines = expected_stdout_or_stderr

    has_error: bool = False

    if len(actual_lines) != len(expected_lines):
        has_error = True

    for actual, expected in zip(actual_lines, expected_lines):
        # TODO
        # We check endswith to avoid the ANSI chars, but this could be better
        if not actual.endswith(expected):
            has_error = True

    if has_error:
        print("actual output:")
        print("\n".join(actual_lines))
        print("----------")
        print("expected output:")
        print("\n".join(expected_lines))
        return False

    return True
