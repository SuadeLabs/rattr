"""Hold ratter chache classes."""

from dataclasses import dataclass, field
from os.path import isfile
from platform import python_version
from typing import Dict, List, Optional, Set, Type, TypeVar

import jsonpickle

from ratter.analyser.types import FileIR, FileResults
from ratter.cache.util import (
    get_cache_filepath,
    get_file_hash,
    get_import_filepaths,
)
from ratter.version import __version__

_FileCache = TypeVar("_FileCache", bound="FileCache")


import_info_by_filepath: Dict[str, Dict[str, str]] = dict()


@dataclass
class FileCache:
    """Store the cache for a specific file.

    The cache is designed to be JSON serialisable/un-serialisable.

    Cache format (JSON, not accounting for `jsonpickle` data):
    ```json
    {
        "ratter_version": ...,  # the Ratter version the cache was created by
        "python_version": ...,  # the Python version Ratter was run under

        "filepath": ...,        # the file the results belong to
        "filehash": ...,        # the MD5 hash of the file when it was cached

        "imports": [
            {"filename": ..., "filehash": ...,},
        ],

        "errors": [
            ...                 # the errors produced while analysing the file
        ],

        "ir": {
            ...                 # the IR for the analysed file
        },

        "results":
            ...                 # the results for the analysed file
        },
    }
    ```

    """

    ratter_version: str = __version__
    python_version: str = field(default_factory=python_version)

    filepath: str = "undefined"
    filehash: str = "undefined"

    imports: List[Dict[str, str]] = field(default_factory=list)

    errors: List[str] = field(default_factory=list)

    ir: Optional[FileIR] = None

    results: Optional[FileResults] = None

    def set_file_info(self, filepath: str) -> None:
        """Set the file info for this cache to that of the given file."""
        self.filepath = filepath
        self.filehash = get_file_hash(filepath)

    def set_imports(self) -> None:
        """Set the file imports for this cache.

        NOTE Assumes `config.cache` is complete, see `get_import_filepaths`.

        """
        for i_filepath in get_import_filepaths(self.filepath):
            if i_filepath not in import_info_by_filepath:
                import_info_by_filepath[i_filepath] = {
                    "filepath": i_filepath,
                    "filehash": get_file_hash(i_filepath),
                }

            self.imports.append(import_info_by_filepath[i_filepath])

    def add_error(self, error: str) -> None:
        """Add the given error to the file cache."""
        self.errors.append(error)

    def display_errors(self) -> None:
        """Display the errors for the given cache."""
        for error in self.errors:
            print(error)

    @property
    def is_valid(self) -> bool:
        """Return `True` if the cache is valid.

        If `self.filepath` is unset then `is_valid` is always `False`.

        """
        if self.filepath is None or self.filepath == "undefined":
            return False

        if not isfile(self.filepath):
            return False

        # Validate version
        if self.ratter_version != __version__:
            return False

        if self.python_version != python_version():
            return False

        # Validate file
        if self.filehash != get_file_hash(self.filepath):
            return False

        # Validate imports
        for i in self.imports:
            i_filepath, i_filehash = i.get("filepath"), i.get("filehash")

            if i_filepath is None or i_filehash is None:
                return False

            if i_filehash != get_file_hash(i_filepath):
                return False

        return True

    @classmethod
    def from_file(
        cls: Type[_FileCache], cache_filepath: str, display_errors: bool = True
    ) -> _FileCache:
        """Return the instance storing the cache from the given file.

        NOTE On Security
            Both jsonpickle and Python's provided pickle have notices on being
            insecure [1,2]. Please see them for more information.

        [1] - https://docs.python.org/3/library/pickle.html
        [2] - http://jsonpickle.github.io/index.html#jsonpickle-usage

        If `display_errors` is `True` (default) then the cached errors are
        shown if the existing cache is loaded.

        """
        from ratter import config

        if not config.use_cache:
            raise RuntimeError("unable to read cache when config.use_cache is false")

        if not isfile(cache_filepath):
            raise FileNotFoundError(cache_filepath)

        with open(cache_filepath, "r") as f:
            data = f.read()

        loaded_cache: FileCache = jsonpickle.decode(data)

        if display_errors:
            loaded_cache.display_errors()

        return loaded_cache

    def to_file(self, cache_filepath: Optional[str] = None) -> None:
        """Write the current cache to the disk.

        If `cache_filepath` is `None`, then the default file location for cache
        files will be used.
        See `util.get_cache_filepath(...)`.

        If the cache is not fully populate for all files, then the saved
        imports for this file may be incorrect, see `self.set_imports`.

        """
        from ratter import config

        if not config.save_cache:
            raise RuntimeError("unable to read cache when config.save_cache is false")

        if cache_filepath is None:
            cache_filepath = get_cache_filepath(self.filepath)

        # NOTE
        #   Set cache imports, now is the best time as it is as populated as it
        #   will be
        self.set_imports()

        with open(cache_filepath, "w") as f:
            f.write(jsonpickle.encode(self, indent=4))


@dataclass
class RatterCache:
    changed: Set[str] = field(default_factory=set)
    cache_by_file: Dict[str, FileCache] = field(default_factory=dict)

    def has(self, filepath: str) -> bool:
        """Return `True` if there is an up-to-date cache of the given file."""
        return self.get(filepath) is not None

    def get(self, filepath: str) -> Optional[FileCache]:
        """Return the cache for the given file.

        Priority:
            1. the currently loaded caches (`self.cache_by_file`)
            2. the cache file in the expected location, if valid
            3. there is no cache

        Side-effect:
            On reaching priority 2, if the cache file exists and the contained
            cache is valid then it will be read and loaded into
            `self.cache_by_file`.

        """
        from ratter import config

        if filepath in self.cache_by_file:
            return self.cache_by_file[filepath]

        if config.use_cache:
            try:
                cache = FileCache.from_file(get_cache_filepath(filepath))
            except FileNotFoundError:
                return None

            if not cache.is_valid:
                return None

            if cache.filepath != filepath:
                raise ValueError(
                    f"cache filepath does not match real filepath, "
                    f"'{cache.filepath}' != '{filepath}'"
                )

            return cache

        return None

    def new(self, filepath: str) -> FileCache:
        """Return and register a new cache for the given filepath."""
        if self.has(filepath):
            raise ValueError(f"cache for '{filepath}' already loaded")

        self.cache_by_file[filepath] = FileCache()
        self.cache_by_file[filepath].set_file_info(filepath)

        self.changed.add(filepath)

        return self.cache_by_file[filepath]

    def get_or_new(self, filepath: str) -> FileCache:
        """Return the cache for the given file, creating if needed."""
        return self.get(filepath) or self.new(filepath)

    def write(self) -> None:
        """Write all caches to their default locations.

        NOTE
            If an directly or indirectly imported file's cache is not
            populated, then it will be excluded from the file cache's imports,
            as such this should be called once, when analysis and cache
            construction are complete.
            See `cache.to_file`.

        """
        for filepath, cache in self.cache_by_file.items():
            if filepath in self.changed:
                cache.to_file()
