from __future__ import annotations

# FileResults relies on FunctionResults
# isort: off
from .function import FunctionResults

# isort: on
from .file import FileResults, FunctionName

__all__ = [
    "FunctionResults",
    "FileResults",
    "FunctionName",
]
