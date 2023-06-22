from __future__ import annotations

import ast
from typing import Dict, Literal, Set, Union

from typing_extensions import TypeAlias

from rattr.analyser.context.symbol import Class, Func, Symbol
from rattr.models.ir import FileIr

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


FunctionIr = Dict[ResultsCategory, Set[Symbol]]
"""The intermediate representation for a function."""

ClassIr = Dict[Union[Func, Class], FunctionIr]
"""The intermediate representation for a class."""


_ModuleName: TypeAlias = str
ImportsIr = Dict[_ModuleName, FileIr]


_Identifier: TypeAlias = str
FunctionResults = Dict[ResultsCategory, Set[_Identifier]]


_FunctionName: TypeAlias = str
FileResults = Dict[_FunctionName, FunctionResults]
