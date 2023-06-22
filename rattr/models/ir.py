from __future__ import annotations

import json
from typing import TYPE_CHECKING

from rattr.analyser.context.symbol import Symbol

if TYPE_CHECKING:
    from typing import (
        Dict,
        ItemsView,
        Iterator,
        KeysView,
        Optional,
        Union,
        ValuesView,
    )

    from rattr.analyser.context.symbol import Class, Func
    from rattr.analyser.types import FunctionIR

    _FileIR = Dict[Union[Func, Class], FunctionIR]


class FileIr:
    """Provide a `Mapping[Func, FunctionIR]`, with context."""

    def __init__(self, context):
        # `self.context: Context` omitted to avoid circular import, hopefully
        # mypy's inference is sufficient
        self.context = context
        self._file_ir: _FileIR = dict()

    def __eq__(self, other) -> bool:
        if isinstance(other, dict):
            return other == self._file_ir

        if isinstance(other, FileIr):
            return other.context == self.context and other._file_ir == self._file_ir

        raise TypeError(f"Cannot compare 'FileIR' and '{type(other)}'")

    def __iter__(self) -> Iterator[Func | Class]:
        return iter(self._file_ir)

    def __contains__(self, item: Func | Class) -> bool:
        return item in self._file_ir

    def __setitem__(self, item: Func | Class, value: FunctionIR) -> None:
        self._file_ir[item] = value

    def __getitem__(self, item: Func | Class) -> FunctionIR:
        return self._file_ir[item]

    def get(
        self, item: Func | Class, default: Optional[FunctionIR] = None
    ) -> Optional[FunctionIR]:
        return self._file_ir.get(item, default)

    def keys(self) -> KeysView[Func | Class]:
        return self._file_ir.keys()

    def values(self) -> ValuesView[FunctionIR]:
        return self._file_ir.values()

    def items(self) -> ItemsView[Func | Class, FunctionIR]:
        return self._file_ir.items()

    class JsonEncoder(json.JSONEncoder):
        """JSON encoder for FileIR."""

        def default(self, obj):
            if isinstance(obj, (set, list)):
                return sorted(obj)
            if isinstance(obj, Symbol):
                return repr(obj)
            return super().default(obj)

    def __str__(self) -> str:
        cleaned = {repr(k): v for k, v in self._file_ir.items()}

        return json.dumps(cleaned, indent=4, cls=FileIr.JsonEncoder)

    def __repr__(self) -> str:
        return f"FileIR(context={self.context}, _file_ir={self._file_ir}"
