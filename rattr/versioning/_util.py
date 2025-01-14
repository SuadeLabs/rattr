from __future__ import annotations

import operator
import sys
from itertools import takewhile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from rattr.versioning.typing import TypeAlias

    _Operator: TypeAlias = Callable[[str, str], bool]


_DOT_LEXEMES = (".",)
_OPERATOR_LEXEMES = (">", "<", "=")
_DIGIT_LEXEMES = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0")

_OPERATORS: dict[str, _Operator] = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "=": operator.eq,
    "==": operator.eq,
    "!=": operator.ne,
}


def _version_cmp(op: _Operator, current: str, target: str) -> bool:
    _, current_minor_and_micro = current.split(".", maxsplit=1)
    _, target_minor_and_micro = target.split(".", maxsplit=1)
    return op(float(current_minor_and_micro), float(target_minor_and_micro))


def _parse_opcode(version: str) -> tuple[str, str]:
    opcode = "".join(takewhile(lambda c: c in _OPERATOR_LEXEMES, version))
    remainder = version[len(opcode) :]

    return opcode, remainder


def _parse_numeric(version: str) -> tuple[str, str]:
    numeric = "".join(takewhile(lambda c: c in _DOT_LEXEMES + _DIGIT_LEXEMES, version))
    remainder = version[len(numeric) :]

    return numeric, remainder


def _parse_version_string(raw: str) -> tuple[str, str]:
    if len(raw) < 1:
        raise ValueError("version must not be empty")

    _remainder = "".join(c for c in raw if not c.isspace())

    opcode, _remainder = _parse_opcode(_remainder)
    version, _remainder = _parse_numeric(_remainder)

    if not opcode:
        opcode = "=="

    if opcode not in _OPERATORS:
        raise ValueError(f"invalid operator: {opcode}")

    _parts = version.split(".")
    _parts_are_well_formed = all(p.isnumeric() for p in _parts)

    if (
        _remainder
        or not version
        or len(_parts) not in (2, 3)
        or not _parts_are_well_formed
        or not _parts[0] == "3"
    ):
        raise ValueError(f"malformed version: {raw}, expects '(<op>)?3.x(.y)?'")

    return opcode, version


def _current_version() -> tuple[int, int, int]:
    return sys.version_info.major, sys.version_info.minor, sys.version_info.micro


def _current_version_string(*, include_micro: bool = False) -> str:
    major, minor, micro = _current_version()

    if include_micro:
        return f"{major}.{minor}.{micro}"

    return f"{major}.{minor}"


def is_python_version(version: str) -> bool:
    opcode, target_version = _parse_version_string(version)

    include_micro = len(target_version.split(".")) == 3

    operator = _OPERATORS[opcode]
    interpreter_version = _current_version_string(include_micro=include_micro)

    return _version_cmp(operator, interpreter_version, target_version)
