import hashlib
import mock
import pytest
import tempfile
from itertools import combinations
from pathlib import Path

from ratter.analyser.context.symbol import Import
from ratter.cache.cache import FileCache, RatterCache
from ratter.cache.util import get_cache_filepath, get_file_hash
from ratter.version import __version__


def get_cache_filepath_safe(filepath: str) -> str:
    return get_cache_filepath(filepath, mkdir=False)


def mocked_cache(**kwargs):
    m_cache = mock.Mock(spec=FileCache)

    for kw, arg in kwargs.items():
        setattr(m_cache, kw, arg)

    return m_cache


class TestFileCache:

    def test_set_file_info(self):
        cache = FileCache()

        assert cache.filepath == "undefined"
        assert cache.filehash == "undefined"

        cache.set_file_info(__file__)

        assert cache.filepath == __file__
        assert cache.filehash == get_file_hash(__file__)

    def test_set_imports(self):
        raise AssertionError

    def test_errors(self, capsys):
        # Test set errors
        cache = FileCache()

        assert cache.errors == list()

        cache.add_error("error: this is my error")
        cache.add_error("error: this is another error")
        cache.add_error("warning: i must warn you, i am the last")

        assert cache.errors == [
            "error: this is my error",
            "error: this is another error",
            "warning: i must warn you, i am the last",
        ]

        # Test display errors
        cache.display_errors()
        output, _ = capsys.readouterr()

        assert output == "".join(
            line + "\n" for line in
            [
                "error: this is my error",
                "error: this is another error",
                "warning: i must warn you, i am the last",
            ]
        )

    def test_errors_integration(self, capsys):
        from ratter import config, error

        assert isinstance(config.cache, RatterCache)

        config.current_file = __file__
        cache = config.cache.get_or_new(__file__)
        other_cache = config.cache.get_or_new(
            Path(__file__).parent / "test_base.py"
        )

        error.error("test error")
        error.warning("test warning")

        # Errors are added to __file__ errors but not to the redherring cache
        real_output: str = capsys.readouterr()[0]
        assert cache.errors == real_output.splitlines()
        assert other_cache.errors == list()

        # Display errors works, output only prints since last call
        cache.display_errors()
        cached_output: str = capsys.readouterr()[0]
        assert cached_output == real_output

    def test_is_valid(self):
        __hash__ = get_file_hash(__file__)

        # self.filepath is unset
        assert not FileCache().is_valid
        assert not FileCache(filepath=None).is_valid

        # self.filepath is not a file
        assert not FileCache(filepath="not-a-file").is_valid

        # self.ratter_version is incorrect
        file_cache = FileCache(
            filepath=__file__,
            filehash=__hash__,
        )
        assert file_cache.is_valid
        file_cache.ratter_version = "Cheesed to meet you"
        assert not file_cache.is_valid

        # self.python_version is incorrect
        file_cache = FileCache(
            filepath=__file__,
            filehash=__hash__,
        )
        assert file_cache.is_valid
        file_cache.ratter_version = "The Wrong Trousers"
        assert not file_cache.is_valid

        # self.filehash is incorrect
        file_cache = FileCache(
            filepath=__file__,
            filehash=__hash__,
        )
        assert file_cache.is_valid
        file_cache.filehash = "The Curse of the Were-Rabbit"
        assert not file_cache.is_valid

        # self.imports
        with mock.patch("ratter.cache.cache.get_file_hash") as m_get_file_hash:
            file_cache = FileCache(
                filepath=__file__,
                filehash=__hash__,
            )

            # Empty
            m_get_file_hash.side_effect = [
                __hash__,
                FileNotFoundError,
            ]
            assert file_cache.is_valid

            # Incorrect
            file_cache.imports = [
                {
                    "filepath": "first import",
                    "filehash": "first import hash",
                },
                {
                    "filepath": "second import",
                    "filehash": "second import hash",
                },
            ]
            m_get_file_hash.side_effect = [
                __hash__,
                "NOT first import hash",
                "NOT second import hash",
                FileNotFoundError,
            ]
            assert not file_cache.is_valid

            # Correct
            m_get_file_hash.side_effect = [
                __hash__,
                "first import hash",
                "second import hash",
                FileNotFoundError,
            ]
            assert file_cache.is_valid


class TestRatterCache:

    def test_has(self):
        assert not RatterCache().has("nope")

        populated = RatterCache(cache_by_file={"file": mock.Mock()})
        assert populated.has("file")
        assert not populated.has("some_other_file")

    def test_get(self, config):
        # Does not exist
        assert RatterCache().get("nope") is None

        populated = RatterCache(cache_by_file={"file": mock.Mock()})

        # Has been loaded or created
        assert populated.get("file") is not None
        assert populated.get("some_other_file") is None

        # Load from file
        with config("use_cache", True):
            with mock.patch("ratter.cache.cache.FileCache") as m_FileCache:
                m_cache = mocked_cache(
                    filepath="loaded_file",
                    is_valid=True,
                )
                m_FileCache.from_file.side_effect = [
                    m_cache,
                    AssertionError,
                ]

                assert populated.get("loaded_file") is not None

        # Load from file, file does not exist
        with config("use_cache", True):
            with mock.patch("ratter.cache.cache.FileCache") as m_FileCache:
                m_cache = mocked_cache(
                    filepath="loaded_file",
                    is_valid=True,
                )
                m_FileCache.from_file.side_effect = [
                    FileNotFoundError,
                ]

                assert populated.get("loaded_file") is None

        # Load from file, file is outdated
        with config("use_cache", True):
            with mock.patch("ratter.cache.cache.FileCache") as m_FileCache:
                m_cache = mocked_cache(
                    filepath="loaded_file",
                    is_valid=False,
                )
                m_FileCache.from_file.side_effect = [
                    m_cache,
                    AssertionError,
                ]

                assert populated.get("loaded_file") is None

        # Load from file, filepath mismatch
        with config("use_cache", True):
            with mock.patch("ratter.cache.cache.FileCache") as m_FileCache:
                m_cache = mocked_cache(
                    filepath="THE WRONG FILE PATH",
                    is_valid=True,
                )
                m_FileCache.from_file.side_effect = [
                    m_cache,
                    AssertionError,
                ]

                with pytest.raises(ValueError):
                    populated.get("loaded_file") is None

        # Post-tests changes should be empty
        assert populated.changed == set()

    def test_new(self):
        ratter_cache = RatterCache()

        assert ratter_cache.get("my_file") is None
        assert ratter_cache.changed == set()
        assert ratter_cache.cache_by_file == dict()

        assert ratter_cache.new("my_file") is not None
        assert ratter_cache.changed == {"my_file"}
        assert ratter_cache.cache_by_file["my_file"] is not None

    def test_get_or_new(self):
        ratter_cache = RatterCache()
        existant = ratter_cache.new("existing")

        # Get existant
        assert ratter_cache.get_or_new("existing") == existant

        # Get non-existant
        non_existant = ratter_cache.get_or_new("non_existant")
        assert non_existant is not None
        assert non_existant != existant
        assert non_existant.filepath == "non_existant"


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
