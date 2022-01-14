import hashlib
import os
import tempfile
from itertools import combinations
from pathlib import Path

from ratter.analyser.context.symbol import Import
from ratter.cache.util import get_cache_filepath, get_file_hash


def get_cache_filepath_safe(filepath: str) -> str:
    return get_cache_filepath(filepath, mkdir=False)


class TestFileCache:

    def test_set_file_info(self):
        raise AssertionError

    def test_set_imports(self):
        raise AssertionError

    def test_add_error(self):
        raise AssertionError

    def test_display_errors(self):
        raise AssertionError

    def test_is_valid(self):
        raise AssertionError



class TestRatterCache:

    def test_has(self):
        raise AssertionError

    def test_get(self):
        raise AssertionError

    def test_new(self):
        raise AssertionError

    def test_get_or_new(self):
        raise AssertionError


class TestCacheUtils:

    def test_get_file_hash_no_file(self):
        assert get_file_hash("i-do-not-exist") is None
    
    def test_get_file_hash_sanity(self):
        # Get MD5 of raw file
        with open(__file__, "rb") as f:
            _hash = hashlib.md5()
            _hash.update(f.read())

        hashes = [
            _hash.hexdigest(),              # full file in one buffer
            get_file_hash(__file__, 2**9),  # 500KiB blocks
            get_file_hash(__file__, 2**10), # 1MiB blocks
            get_file_hash(__file__, 2**11), # 2MiB blocks
        ]

        # Make sure that __file__ is hashed correctly
        assert all(h is not None for h in hashes)

        # Assert that all hashes are equal
        for lhs, rhs in combinations(hashes, 2):
            assert lhs == rhs

    def test_get_cache_filepath(self):
        tmp = tempfile.gettempdir()

        # Is pip module
        filepath = get_cache_filepath_safe(Import("flask").module_spec.origin)
        rel_libpath = Path(Import("flask").module_spec.origin[1:]).parent
        assert filepath.startswith(tmp)
        assert filepath == str(
            Path(tmp) / ".ratter" / "cache" / rel_libpath / "__init__.json"
        )

        # Is stdlib module
        filepath = get_cache_filepath_safe(Import("pathlib").module_spec.origin)
        rel_libpath = Path(Import("pathlib").module_spec.origin[1:]).parent
        assert filepath.startswith(tmp)
        assert filepath == str(
            Path(tmp) / ".ratter" / "cache" / rel_libpath / "pathlib.json"
        )

        SOURCE = Path(__file__).parent.parent / "ratter" /  "cache"
        BASE = SOURCE / ".ratter" / "cache"

        # Is local module
        filepath = get_cache_filepath_safe(
            Import("ratter.cache.cache").module_spec.origin
        )
        assert not filepath.startswith(tmp)
        assert filepath == str(BASE / "cache.json")

        # Is local module, __init__.py
        filepath = get_cache_filepath_safe(
            Import("ratter.cache").module_spec.origin
        )
        assert not filepath.startswith(tmp)
        assert filepath == str(BASE / "__init__.json")

        # mkdir=True
        cachepath = BASE / "cache.json"
        assert not cachepath.parent.is_dir()
        filepath = get_cache_filepath(
            Import("ratter.cache.cache").module_spec.origin
        )
        assert cachepath.parent.is_dir()

        # Clean-up
        cachepath.parent.rmdir()
        assert not cachepath.parent.is_dir()
