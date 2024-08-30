from __future__ import annotations

import json
from os.path import isfile
from pathlib import Path
from typing import TYPE_CHECKING

from rattr import error
from rattr._version import version
from rattr.config import Config
from rattr.models.results import FileResults
from rattr.models.results.cacheable import (
    CacheableImportInfo,
    CacheableResults,
    HashableArguments,
    HashablePlugins,
)
from rattr.models.symbol import Import
from rattr.models.symbol._util import PYTHON_BUILTINS_LOCATION
from rattr.models.util.hash import (
    hash_file_content,
    hash_python_objects_type_and_source_files,
    hash_string,
)
from rattr.models.util.serialise import deserialise
from rattr.module_locator.util import is_in_import_blacklist
from rattr.plugins import plugins

if TYPE_CHECKING:
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
        filehash=hash_file_content(target_ir.context.file),
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
    return hash_string(str(hashable_arguments))


def make_plugins_hash() -> str:
    config = Config()
    hashable_plugins = HashablePlugins(
        assertors_hash=hash_python_objects_type_and_source_files(
            plugins.assertors,
            name_of_object=lambda p: p.__class__.__name__,
        ),
        analysers_hash=hash_python_objects_type_and_source_files(
            plugins.analysers,
            name_of_object=lambda p: p.qualified_name,
        ),
        plugins_blacklist_patterns=sorted(config.PLUGINS_BLACKLIST_PATTERNS),
    )
    return hash_string(str(hashable_plugins))


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


def target_cache_file_is_up_to_date(
    target: str | Path,
    cache_filepath: str | Path,
) -> bool:
    """Return `True` if the cache has the correct hash."""
    if not isfile(target):
        error.info(f"cache target {str(target)} does not exist")
        return False

    if not isfile(cache_filepath):
        error.info(f"cache file {str(cache_filepath)} does not exist")
        return False

    try:
        cache = deserialise(Path(cache_filepath).read_text(), type=CacheableResults)
    except json.decoder.JSONDecodeError:
        error.info(f"cache file {str(cache_filepath)} is malformed")
        return False

    return (
        cache.version == version
        and cache.arguments_hash == make_arguments_hash()
        and cache.plugins_hash == make_plugins_hash()
        and cache.filepath == target
        and cache.filehash == hash_file_content(target)
        and all(
            import_info.filehash == hash_file_content(import_info.filepath)
            for import_info in cache.imports
        )
    )
