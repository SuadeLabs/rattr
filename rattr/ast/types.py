from __future__ import annotations

import ast
from typing import Union

from typing_extensions import TypeAlias

Identifier: TypeAlias = str


AstLiterals = (
    ast.JoinedStr,
    ast.List,
    ast.Tuple,
    ast.Set,
    ast.Dict,
)
"""AST nodes which represent literals."""

AnyLiteral: TypeAlias = Union[
    ast.FormattedValue,
    ast.JoinedStr,
    ast.List,
    ast.Tuple,
    ast.Set,
    ast.Dict,
]
"""An AST literal node."""


AstComprehensions = (
    ast.ListComp,
    ast.SetComp,
    ast.GeneratorExp,
    ast.DictComp,
)
"""AST nodes which represent comprehensions."""

AnyComprehension: TypeAlias = Union[
    ast.ListComp,
    ast.SetComp,
    ast.GeneratorExp,
    ast.DictComp,
]
"""An AST comprehension node."""


AstFunctionDef = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
)
"""An AST function definition (excludes lambdas)."""

AstFunctionDefOrLambda = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Lambda,
)
"""An AST function definition (includes lambdas)."""


AnyDef: TypeAlias = Union[
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
]
"""An AST function/class definition node."""

AnyFunctionDef: TypeAlias = Union[
    ast.FunctionDef,
    ast.AsyncFunctionDef,
]
"""An AST function definition node (excluding lambdas)."""


AnyAssign = Union[
    ast.Assign,
    ast.AnnAssign,
    ast.AugAssign,
    ast.NamedExpr,
]
"""An AST assignment node."""


AstStrictlyNameable = (
    ast.Name,
    ast.Attribute,
    ast.Subscript,
    ast.Starred,
    ast.Call,
)
"""AST nodes whose exact name can be resolved (via `node.id`, etc)."""


AstCompoundNameable = (
    ast.Attribute,
    ast.Subscript,
    ast.Starred,
)

CompoundNameable: TypeAlias = Union[
    ast.Attribute,
    ast.Subscript,
    ast.Starred,
]
"""An AST node which contains a nameable component."""

Nameable: TypeAlias = ast.expr
"""An `ast.expr` whose "name" can be resolved."""
