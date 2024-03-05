from __future__ import annotations

import attrs


@attrs.frozen
class ModuleSpec:
    name: str
    origin: str | None
