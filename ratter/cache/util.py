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


def get_cache_filepath(filepath: str, mkdir: bool = True) -> str:
    """Return the default cache filepath corresponding to the given file.

    Side-effect:
        The parent directory of the returned path will be created unless
        `mkdir` is explicitly set to `False`.

    """
    dir_as_path = Path(filepath).parent
    file_as_path = Path(filepath).with_suffix(".json").name

    # NOTE
    #   We don't really want to be clogging up /usr/lib/pypy and such with
    #   cache files... So set to /tmp/.ratter/cache/usr/lib/pypy/* or OS
    #   equivalent.
    # NOTE Python Version Compatibility
    #   `Path.parents` does not support splicing or negative indexing pre-3.10,
    #   thus it is converted to a list.
    #   https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.parents
    if filepath in DO_NOT_CACHE:
        raise ValueError(f"can't cache built-in module at '{filepath}'")
    elif is_pip_filepath(filepath) or is_stdlib_filepath(filepath):
        tmp = Path(tempfile.gettempdir())
        libpath = dir_as_path.relative_to(list(dir_as_path.parents)[-1])
        new_dir_as_path = tmp / ".ratter" / "cache" / libpath
    else:
        new_dir_as_path = dir_as_path / ".ratter" / "cache"

    # NOTE Create the containing path if it does not exist
    if mkdir and not new_dir_as_path.is_dir():
        new_dir_as_path.mkdir(parents=True)

    return str(new_dir_as_path / file_as_path)


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
