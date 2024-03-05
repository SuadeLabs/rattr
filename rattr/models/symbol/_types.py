from __future__ import annotations

from typing import Union

from rattr.models.symbol._symbols import Builtin, Class, Func, Import
from rattr.versioning.typing import TypeAlias

CallableSymbol: TypeAlias = Union[Builtin, Class, Func, Import]
UserDefinedCallableSymbol: TypeAlias = Union[Class, Func]
