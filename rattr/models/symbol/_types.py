from __future__ import annotations

from typing import Union

from rattr.models.symbol._symbols import Class, Func
from rattr.versioning.typing import TypeAlias

UserDefinedCallableSymbol: TypeAlias = Union[Func, Class]
