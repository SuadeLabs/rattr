from __future__ import annotations

from typing import Dict, Literal, MutableMapping, Set, Union

from rattr.ast.types import (  # noqa: F401
    AstStrictlyNameable,
    CompoundNameable,
    Nameable,
)
from rattr.models.symbol import Symbol, UserDefinedCallableSymbol
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


FunctionIr: TypeAlias = Dict[ResultsCategory, Set[Symbol]]
"""The intermediate representation for a function."""

ClassIr: TypeAlias = Dict[UserDefinedCallableSymbol, FunctionIr]
"""The intermediate representation for a class."""


_ModuleName: TypeAlias = str
_FileIr: TypeAlias = MutableMapping[UserDefinedCallableSymbol, FunctionIr]
ImportsIr: TypeAlias = Dict[_ModuleName, _FileIr]


_Identifier: TypeAlias = str
FunctionResults: TypeAlias = Dict[ResultsCategory, Set[_Identifier]]


_FunctionName: TypeAlias = str
FileResults: TypeAlias = Dict[_FunctionName, FunctionResults]
