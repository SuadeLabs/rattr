from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import attrs

from rattr.models.context._root_context import (
    MODULE_LEVEL_DUNDER_ATTRS,
    PYTHON_BUILTINS,
)

if TYPE_CHECKING:
    import ast
    from collections.abc import Iterable, Iterator, Mapping
    from typing import Any, Protocol

    from rattr.ast.types import Identifier
    from rattr.models.context import SymbolTable
    from rattr.models.symbol import Symbol

    class MakeSymbolTableFn(Protocol):
        def __call__(
            self,
            symbols: Mapping[Identifier, Symbol] | Iterable[Symbol],
            *,
            include_root_symbols: bool = False,
        ) -> SymbolTable:
            ...

    class ArgumentsFn(Protocol):
        def __call__(
            self,
            **kwargs: Mapping[str, Any],
        ) -> Iterator[None]:
            ...

    class ParseFn(Protocol):
        def __call__(self, source: str) -> ast.Module:
            ...


def compare_symbol_table_symbols(
    lhs: SymbolTable,
    rhs: SymbolTable,
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
