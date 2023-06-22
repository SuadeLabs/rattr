from __future__ import annotations

import ast
from typing import Union

from typing_extensions import TypeAlias

from rattr.versioning import AstNodeNotInPythonVersion, is_python_version

AstConstants = (
    # Python 3.8+ all constants are under `ast.Constant(..., kind=...)`
    ast.Constant,
    # Before Python 3.8, each constant had it's own node type
    ast.Num,
    ast.Str,
    ast.Bytes,
    ast.NameConstant,
    ast.Ellipsis,
)
"""AST nodes which represent constants."""

AnyConstant: TypeAlias = Union[
    # Python 3.8+ all constants are under `ast.Constant(..., kind=...)`
    ast.Constant,
    # Before Python 3.8, each constant had it's own node type
    ast.Num,
    ast.Str,
    ast.Bytes,
    ast.NameConstant,
    ast.Ellipsis,
]
"""An AST constant node."""


AstLiterals = (
    ast.FormattedValue,
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


if is_python_version(">=3.8"):
    AstNamedExpr = ast.NamedExpr
else:
    AstNamedExpr = AstNodeNotInPythonVersion


AnyAssign = Union[
    ast.Assign,
    ast.AnnAssign,
    ast.AugAssign,
    AstNamedExpr,
]
"""An AST assignment node."""
