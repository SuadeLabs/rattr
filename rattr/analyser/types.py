from __future__ import annotations

import ast
from typing import Dict, Literal, MutableMapping, Set, Union

from rattr.models.symbol import Symbol, UserDefinedCallableSymbol
from rattr.versioning.typing import TypeAlias

ResultsCategory: TypeAlias = Literal["gets", "sets", "dels", "calls"]

# Not in `rattr.ast.types` as "nameability" is a rattr concept
AstStrictlyNameable = (
    ast.Name,
    ast.Attribute,
    ast.Subscript,
    ast.Starred,
    ast.Call,
)
"""AST nodes whose exact name can be resolved (via `node.id`, etc)."""

CompoundNameable: TypeAlias = Union[
    ast.Attribute,
    ast.Subscript,
    ast.Starred,
]
"""An AST node which contains a nameable component."""

Nameable: TypeAlias = ast.expr
"""An `ast.expr` whose "name" can be resolved."""

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
