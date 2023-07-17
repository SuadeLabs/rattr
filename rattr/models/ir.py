from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Dict, MutableMapping

import attrs
from attrs import field
from cattr.preconf.json import make_converter

from rattr.analyser.context import Context
from rattr.analyser.types import FunctionIr
from rattr.models.symbol import UserDefinedCallableSymbol

if TYPE_CHECKING:
    from typing import Iterator


_ir_json_converter = make_converter()

_FileIr = Dict[UserDefinedCallableSymbol, FunctionIr]


@attrs.mutable
class FileIr(MutableMapping[UserDefinedCallableSymbol, FunctionIr]):
    """The Intermediate Representation (IR) for the functions/classes in a file."""

    context: Context
    _file_ir: _FileIr = field(default={}, alias="file_ir")

    def ir_as_dict(self) -> _FileIr:
        """Return a copy of the underlying IR dictionary."""
        return copy.deepcopy(self._file_ir)

    def __str__(self) -> str:
        return _ir_json_converter.dumps(self._file_ir)

    # ================================================================================ #
    # Mutable mapping abstract methods and mixin-overrides
    # ================================================================================ #

    def __getitem__(self, __key: UserDefinedCallableSymbol) -> FunctionIr:
        return self._file_ir.__getitem__(__key)

    def __setitem__(
        self,
        __key: UserDefinedCallableSymbol,
        __value: FunctionIr,
    ) -> None:
        return self._file_ir.__setitem__(__key, __value)

    def __delitem__(self, __key: UserDefinedCallableSymbol) -> None:
        return self._file_ir.__delitem__(__key)

    def __iter__(self) -> Iterator[UserDefinedCallableSymbol]:
        return self._file_ir.__iter__()

    def __len__(self) -> int:
        return self._file_ir.__len__()

    def clear(self) -> None:
        """Clear the File IR contents.

        ### Note
        This does not clear the associated context as that makes little sense (one may
        wish to clear the function IRs within but it does not make sense to also destroy
        the namespace).
        If you do wish to clear the context as well, you must do so directly.
        """
        # NOTE
        #   The default mixin clear iterates every key and pops, this is much slower
        #   than deferring to the underlying dictionary clear.
        return self._file_ir.clear()
