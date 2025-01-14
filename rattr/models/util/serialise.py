from __future__ import annotations

from typing import TYPE_CHECKING

from rattr.models.ir import FileIr
from rattr.models.util._serialisation_helpers import make_json_converter
from rattr.models.util._types import FileName, ImportIrs, OutputIrs

if TYPE_CHECKING:
    from typing import Any, TypeVar

    T = TypeVar("T")


__json_converter = make_json_converter()


def serialise(model: Any, **kwargs: Any) -> str:
    return __json_converter.dumps(model, **kwargs)  # type: ignore[reportUnknownMemberType]


def deserialise(json: str, *, type: type[T], **kwargs: Any) -> T:
    return __json_converter.loads(json, cl=type, **kwargs)  # type: ignore[reportUnknownMemberType]


def serialise_irs(
    *,
    target_name: FileName,
    target_ir: FileIr,
    import_irs: ImportIrs,
) -> str:
    return serialise(
        OutputIrs(
            import_irs=import_irs,
            target_ir={"filename": target_name, "ir": target_ir},
        ),
        indent=4,
    )
