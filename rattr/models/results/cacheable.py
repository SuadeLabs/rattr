from __future__ import annotations

import hashlib
import inspect
from os.path import isfile
from typing import TYPE_CHECKING, NamedTuple

import attrs
from attrs import field

from rattr._version import version
from rattr.config import Config
from rattr.models.results import FileResults
from rattr.models.symbol import Import
from rattr.models.symbol._util import PYTHON_BUILTINS_LOCATION
from rattr.module_locator.util import is_in_import_blacklist
from rattr.plugins import plugins

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from typing import TypeVar

    from rattr.analyser.types import ImportIrs
    from rattr.models.ir import FileIr

    T = TypeVar("T")


def make_cacheable_results(
    results: FileResults,
    target_ir: FileIr,
    import_irs: ImportIrs,
) -> CacheableResults:
    return CacheableResults(
        version=version,
        arguments_hash=make_arguments_hash(),  # config.__hash__ is salted
        plugins_hash=make_plugins_hash(),  # plugins.__hash__ is salted
        filepath=target_ir.context.file,
        filehash=make_md5_hash_of_file(target_ir.context.file),
        imports=make_cacheable_import_info(target_ir, import_irs),
        results=results,
    )


def make_arguments_hash() -> str:
    config = Config()
    hashable_arguments = HashableArguments(
        literal_value_prefix=config.LITERAL_VALUE_PREFIX,
        follow_imports_level=config.arguments.follow_imports.value,
        excluded_imports=sorted(config.arguments.excluded_imports),
        excluded_names=sorted(config.arguments.excluded_names),
    )
    return make_md5_hash_from_str(str(hashable_arguments))


def make_plugins_hash() -> str:
    config = Config()
    hashable_plugins = HashablePlugins(
        assertors_hash=make_md5_hash_of_plugins_by_name_and_source_file(
            plugins.assertors,
            name_of_plugin=lambda p: p.__qualname__,
        ),
        analysers_hash=make_md5_hash_of_plugins_by_name_and_source_file(
            plugins.analysers,
            name_of_plugin=lambda p: p.qualified_name,
        ),
        plugins_blacklist_patterns=sorted(config.PLUGINS_BLACKLIST_PATTERNS),
    )
    return make_md5_hash_from_str(str(hashable_plugins))


def make_md5_hash_of_plugins_by_name_and_source_file(
    plugins: list[T],
    *,
    name_of_plugin: Callable[[T], str],
) -> str:
    hash = hashlib.md5()

    for plugin in sorted(plugins, key=lambda p: name_of_plugin(p)):
        hash.update(name_of_plugin(plugin).encode("utf-8"))
        hash.update(inspect.getfile(type(plugin)).encode("utf-8"))

    return hash.hexdigest()


def make_md5_hash_of_file(
    filepath: str | Path,
    *,
    blocksize: int = 2**20,
) -> str:
    hash = hashlib.md5()

    if not isfile(filepath):
        return hash.hexdigest()

    with open(filepath, "rb") as f:
        while True:
            buffer = f.read(blocksize)

            if not buffer:
                break

            hash.update(buffer)

    return hash.hexdigest()


def make_md5_hash_from_str(s: str, /) -> str:
    hash = hashlib.md5()
    hash.update(str(s).encode("utf-8"))
    return hash.hexdigest()


def make_cacheable_import_info(
    target_ir: FileIr,
    import_irs: ImportIrs,
) -> list[CacheableImportInfo]:
    contexts = (
        target_ir.context,
        *(import_.context for import_ in import_irs.values()),
    )

    return sorted(
        {
            CacheableImportInfo.from_file(symbol.module_spec.origin)
            for context in contexts
            for symbol in context.symbol_table.symbols
            if isinstance(symbol, Import)
            if symbol.module_name is not None
            if not is_in_import_blacklist(symbol.module_name)
            if symbol.module_spec is not None
            if symbol.module_spec.origin is not None
            if symbol.module_spec.origin != PYTHON_BUILTINS_LOCATION
        },
        key=lambda info: info.filepath,
    )


@attrs.frozen
class CacheableImportInfo:
    filepath: str = field(converter=str, default="")
    filehash: str = field(default="")

    @classmethod
    def from_file(cls, filepath: str) -> CacheableImportInfo:
        return CacheableImportInfo(
            filepath=filepath,
            filehash=make_md5_hash_of_file(filepath),
        )


@attrs.frozen
class CacheableResults:
    version: str = field(default="")

    arguments_hash: str = field(default="")
    plugins_hash: str = field(default="")

    filepath: str = field(converter=str, default="")
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
