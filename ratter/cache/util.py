"""Ratter cache util functions."""

import hashlib
import tempfile
from os.path import isfile
from pathlib import Path
from typing import List, Optional, Set

from ratter.analyser.context.context import Context
from ratter.analyser.context.symbol import Import
from ratter.analyser.util import is_pip_filepath, is_stdlib_filepath

DO_NOT_CACHE = {"built-in", "frozen"}


def get_file_hash(filepath: str, blocksize: int = 2 ** 20) -> Optional[str]:
    """Return the hash of the given file, with a default blocksize of 1MiB."""
    _hash = hashlib.md5()

    if not isfile(filepath):
        return None

    with open(filepath, "rb") as f:
        while True:
            buffer = f.read(blocksize)

            if not buffer:
                break

            _hash.update(buffer)

    return _hash.hexdigest()


def get_cache_filepath(source_filepath: str, mkdir: bool = True) -> str:
    """Return the default cache filepath corresponding to the given file.

    Side-effect:
        The parent directory of the returned path will be created unless
        `mkdir` is explicitly set to `False`.

    """
    if source_filepath in DO_NOT_CACHE:
        raise ValueError(f"can't cache built-in module at '{source_filepath}'")

    tmp = Path(tempfile.gettempdir())
    source_file_dir = Path(source_filepath).parent
    cache_file_name = Path(source_filepath).with_suffix(".json").name

    # NOTE
    #   We don't want to be clogging up /usr/lib/pypy etc with cache files...
    #   So place pip/stdlib cache files <OS temp>/.ratter/cache/path/to/source
    if is_pip_filepath(source_filepath) or is_stdlib_filepath(source_filepath):
        root = list(source_file_dir.parents)[-1]
        cache_dir = tmp / ".ratter" / "cache" / source_file_dir.relative_to(root)
    else:
        cache_dir = source_file_dir / ".ratter" / "cache"

    # Create the containing path if it does not exist
    if mkdir and not cache_dir.is_dir():
        cache_dir.mkdir(parents=True)

    return str(cache_dir / cache_file_name)


def get_import_filepaths(filepath: str) -> Set[str]:
    """Return all imports in the given file, recursively.

    NOTE Assumes the cache is *fully* populated, see `_get_direct_imports`

    """
    imports: Set[str] = set()
    queue: List[Import] = _get_direct_imports(filepath)

    # BFS imports DAG (ignores cycles) to determine all direct and indirect
    # imports from this file
    for i in queue:
        if i.module_spec is None or i.module_spec.origin is None:
            continue

        i_path = i.module_spec.origin

        if i_path in DO_NOT_CACHE:
            continue

        if i_path in imports:
            continue

        imports.add(i_path)

        queue += _get_direct_imports(i_path)

    return imports


def _get_direct_imports(filepath: str) -> List[Import]:
    """Return the `Import` symbols in the IR of the given file.

    NOTE Assumes the cache is *fully* populated.

    """
    from ratter import config

    if filepath in DO_NOT_CACHE:
        return []

    cached = config.cache.get(filepath)

    if cached is None or cached.ir is None:
        return list()

    ctx: Context = cached.ir.context
    imports: List[Import] = list()

    for symbol in ctx.symbol_table.symbols():
        if isinstance(symbol, Import):
            imports.append(symbol)

    return imports
