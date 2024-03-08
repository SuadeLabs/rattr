from __future__ import annotations

import ast

from rattr.versioning.typing import TypeAlias

Identifier: TypeAlias = str
ModuleName: TypeAlias = str
FullyQualifiedName: TypeAlias = str


AstLiterals = (
    ast.JoinedStr,
    ast.List,
    ast.Tuple,
    ast.Set,
    ast.Dict,
)
"""AST nodes which represent literals."""


AstComprehensions = (
    ast.ListComp,
    ast.SetComp,
    ast.GeneratorExp,
    ast.DictComp,
)
"""AST nodes which represent comprehensions."""


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


AstNodeWithName = (
    ast.Name,
    ast.Attribute,
    ast.Subscript,
    ast.Starred,
    ast.Call,
)
"""AST nodes whose exact name can be resolved (via `node.id`, etc)."""
