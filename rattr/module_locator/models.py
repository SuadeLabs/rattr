from __future__ import annotations

from typing import NamedTuple


class ModuleSpec(NamedTuple):
    name: str
    origin: str | None
