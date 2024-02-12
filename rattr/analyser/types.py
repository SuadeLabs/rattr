from __future__ import annotations

from typing import Literal, Union

from rattr.ast.types import (  # noqa: F401
    AstStrictlyNameable,
    CompoundNameable,
    Identifier,
    Nameable,
)
from rattr.models.ir import FileIr, FunctionIr
from rattr.models.symbol import UserDefinedCallableSymbol
from rattr.versioning.typing import TypeAlias

ResultsCategory: TypeAlias = Literal["gets", "sets", "dels", "calls"]


PythonLiteral: TypeAlias = Union[
    None,
    int,
    float,
    complex,
    bool,
    str,
    bytes,
]
"""Python literals."""

ClassIr: TypeAlias = dict[UserDefinedCallableSymbol, FunctionIr]
"""The intermediate representation for a class."""


_ModuleName: TypeAlias = str
ImportsIr: TypeAlias = dict[_ModuleName, FileIr]
