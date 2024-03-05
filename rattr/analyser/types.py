from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from rattr.ast.types import (  # noqa: F401
    Identifier,
)
from rattr.models.ir import FileIr, FunctionIr
from rattr.models.symbol import UserDefinedCallableSymbol
from rattr.versioning.typing import TypeAlias

if TYPE_CHECKING:
    from rattr.versioning.typing import TypeAlias


ClassIr: TypeAlias = dict[UserDefinedCallableSymbol, FunctionIr]

_ModuleName: TypeAlias = str
ImportIrs: TypeAlias = dict[_ModuleName, FileIr]


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
