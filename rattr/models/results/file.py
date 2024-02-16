from __future__ import annotations

from typing import Iterator, MutableMapping

import attrs
from attrs import field
from typing_extensions import TypeAlias

from rattr.models.results.function import FunctionResults

FunctionName: TypeAlias = str


@attrs.mutable
class FileResults(MutableMapping[FunctionName, FunctionResults]):
    _function_results: dict[FunctionName, FunctionResults] = field(
        alias="function_results",
        factory=dict,
    )

    # ================================================================================ #
    # Mutable mapping abstract methods and mixin-overrides
    # ================================================================================ #

    def __getitem__(self, __key: FunctionName) -> FunctionResults:
        return self._function_results.__getitem__(__key)

    def __setitem__(
        self,
        __key: FunctionName,
        __value: FunctionResults,
    ) -> None:
        return self._function_results.__setitem__(__key, __value)

    def __delitem__(self, __key: FunctionName) -> None:
        return self._function_results.__delitem__(__key)

    def __iter__(self) -> Iterator[FunctionName]:
        return self._function_results.__iter__()

    def __len__(self) -> int:
        return self._function_results.__len__()

    def clear(self) -> None:
        # NOTE Better than derived implementation
        return self._function_results.clear()
