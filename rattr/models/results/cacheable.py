from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import attrs
from attrs import field

from rattr.models.results import FileResults
from rattr.models.util.hash import hash_file_content


@attrs.frozen
class CacheableImportInfo:
    filepath: Path = field(converter=Path, factory=Path)
    filehash: str = field(default="")

    @classmethod
    def from_file(cls, filepath: str | Path) -> CacheableImportInfo:
        return CacheableImportInfo(
            filepath=filepath,
            filehash=hash_file_content(filepath),
        )


@attrs.frozen
class CacheableResults:
    version: str = field(default="")

    arguments_hash: str = field(default="")
    plugins_hash: str = field(default="")

    filepath: Path = field(converter=Path, factory=Path)
    filehash: str = field(default="")

    imports: list[CacheableImportInfo] = field(factory=list)
    results: FileResults = field(factory=FileResults)


class HashableArguments(NamedTuple):
    literal_value_prefix: str
    follow_imports_level: int
    excluded_imports: list[str]
    excluded_names: list[str]


class HashablePlugins(NamedTuple):
    assertors_hash: str
    analysers_hash: str
    plugins_blacklist_patterns: list[str]
