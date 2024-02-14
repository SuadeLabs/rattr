from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict, Union

from rattr.ast.types import (  # noqa: F401
    AstStrictlyNameable,
    CompoundNameable,
    Identifier,
    Nameable,
)
from rattr.models.ir import FileIr, FunctionIr
from rattr.models.symbol import UserDefinedCallableSymbol
from rattr.versioning.typing import TypeAlias

if TYPE_CHECKING:
    from typing_extensions import TypeAlias

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

_ModuleName: TypeAlias = str
ImportsIr: TypeAlias = dict[_ModuleName, FileIr]


TargetName: TypeAlias = Identifier
PositionalArgumentName: TypeAlias = Identifier
KeywordArgumentName: TypeAlias = Identifier
LocalIdentifier: TypeAlias = Identifier


class RattrResults(TypedDict):
    gets: set[Identifier]
    sets: set[Identifier]
    dels: set[Identifier]
    calls: list[
        tuple[
            TargetName,
            tuple[
                list[PositionalArgumentName],
                dict[KeywordArgumentName, LocalIdentifier],
            ],
        ]
    ]
