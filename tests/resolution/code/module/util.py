from __future__ import annotations

from module.constants import CONSTANT


def get_constant() -> int:
    return CONSTANT.get("blah", 0)
