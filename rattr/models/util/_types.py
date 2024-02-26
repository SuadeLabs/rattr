from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

import attrs

from rattr.models.ir import FileIr

if TYPE_CHECKING:
    from rattr.versioning.typing import TypeAlias


FileName: TypeAlias = str
ModuleName: TypeAlias = str

ImportIrs: TypeAlias = dict[ModuleName, FileIr]


class TargetIr(TypedDict):
    filename: FileName
    ir: FileIr


@attrs.frozen
class OutputIrs:
    import_irs: ImportIrs
    target_ir: TargetIr
