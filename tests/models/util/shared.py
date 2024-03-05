from __future__ import annotations

from typing import NamedTuple


class CallInterfaceArgs(NamedTuple):
    posonlyargs: list[str]
    args: list[str]
    vararg: str | None
    kwonlyargs: list[str]
    kwarg: str | None
