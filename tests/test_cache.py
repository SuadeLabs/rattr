from functools import partial
import hashlib
import mock
import pytest
import tempfile
from itertools import combinations
from pathlib import Path

from ratter.analyser.context.context import Context
from ratter.analyser.context.symbol import Call, Func, Import, Name
from ratter.analyser.types import FileIR
from ratter.cache.cache import import_info_by_filepath, FileCache, RatterCache
from ratter.cache.util import (
    DO_NOT_CACHE,
    get_cache_filepath,
    get_file_hash,
    get_import_filepaths,
    _get_direct_imports,
)
from ratter.version import __version__


def get_cache_filepath_safe(filepath: str) -> str:
    return get_cache_filepath(filepath, mkdir=False)


def mocked_cache(**kwargs):
    m_cache = mock.Mock(spec=FileCache)

    for kw, arg in kwargs.items():
        setattr(m_cache, kw, arg)

    return m_cache


def mocked_module_spec(origin: str):
    m_module_spec = mock.Mock(spec=["origin"])
    m_module_spec.origin = origin

    return m_module_spec


class TestFileCache:

    def test_set_file_info(self):
        cache = FileCache()

        assert cache.filepath == "undefined"
        assert cache.filehash == "undefined"

        cache.set_file_info(__file__)

        assert cache.filepath == __file__
        assert cache.filehash == get_file_hash(__file__)

    @mock.patch("ratter.cache.cache.get_import_filepaths")
    def test_set_imports(self, m_get_import_filepaths):
        m_get_import_filepaths: mock.MagicMock = m_get_import_filepaths

        # Test adding nothing
        m_get_import_filepaths.return_value = set()
        file_cache = FileCache()

        assert file_cache.imports == list()
        file_cache.set_imports()
        assert file_cache.imports == list()

        # Util -- sort by file
        sorted_by_file = partial(sorted, key=lambda info: info["filepath"])

        # Test not in import_info_by_filepath
        # Test set import_info_by_filepath
        with mock.patch("ratter.cache.cache.get_file_hash") as m_get_file_hash:
            assert import_info_by_filepath == dict()

            # Data
            modules = [
                "some_import",
                "another",
                "some.dotted.module",
            ]
            imports = [{"filepath": m, "filehash": f"H({m})"} for m in modules]

            # Mock
            m_get_file_hash.side_effect = lambda f: f"H({f})"
            m_get_import_filepaths.return_value = set(modules)

            # Test
            file_cache = FileCache()
            assert file_cache.imports == list()
            file_cache.set_imports()
            assert sorted_by_file(file_cache.imports) == sorted_by_file(imports)

            # Has set import_info_by_filepath?
            for m in modules:
                assert import_info_by_filepath[m] == {
                    "filepath": m,
                    "filehash": f"H({m})",
                }

        # Test in import_info_by_filepath
        with mock.patch("ratter.cache.cache.import_info_by_filepath") as m_import_info:
            # Data
            modules = [
                "some_import",
                "another",
                "some.dotted.module",
            ]
            imports = [{"filepath": m, "filehash": f"H({m})"} for m in modules]
            import_info = {m: i for m, i in zip(modules, imports)}

            # Mock
            m_import_info.__contains__.side_effect = import_info.__contains__
            m_import_info.__getitem__.side_effect = import_info.__getitem__
            m_get_import_filepaths.return_value = set(modules)

            # Test
            file_cache = FileCache()
            assert file_cache.imports == list()
            file_cache.set_imports()
            assert sorted_by_file(file_cache.imports) == sorted_by_file(imports)

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

    def test_get_import_filepaths_no_imports(self):
        with mock.patch("ratter.cache.util._get_direct_imports") as m_get_imports:
            m_get_imports.side_effect = lambda _: list()
            assert get_import_filepaths("anything") == set()

    def test_get_import_filepaths_direct(self, config):
        """Case of A imports B."""
        # Define B
        b_ctx = Context(None)
        b_lib_func = Func("lib_func", ["a"], None, None)
        b_ctx.add_all([
            Name("I_AM_A_CONSTANT"),
            Name("I_AM_JUST_SHOUTING"),
            b_lib_func,
        ])
        b_ir = FileIR(b_ctx)
        b_ir._file_ir = {
            b_lib_func: {
                "sets": {
                    Name("a.attr", "a"),
                },
                "gets": set(),
                "dels": set(),
                "calls": set(),
            }
        }
        b_cache = FileCache(
            filepath="b.py",
            filehash="H(b.py)",
            ir=b_ir,
        )

        # Define A
        # Import B.lib_func
        a_ctx = Context(None)
        import_lib_func = Import("lib_func", "b.lib_func", "b")
        import_lib_func.module_spec = mocked_module_spec("b.py")
        a_func = Func("a_needs_a_fn_too", ["arg"], None, None)
        a_ctx.add_all([
            import_lib_func,
            Name("var_a"),
            Name("var_b"),
            a_func,
        ])
        a_ir = FileIR(a_ctx)
        a_ir._file_ir = {
            a_func: {
                "sets": set(),
                "gets": {
                    Name("arg.something", "arg"),
                },
                "dels": set(),
                "calls": {
                    Call("lib_func()", ["arg"], {}, target=import_lib_func),
                },
            }
        }
        a_cache = FileCache(
            filepath="a.py",
            filehash="H(a.py)",
            ir=a_ir,
        )

        # New RatterCache
        ratter_cache = RatterCache(
            changed={a_cache.filepath, b_cache.filepath},
            cache_by_file={
                a_cache.filepath: a_cache,
                b_cache.filepath: b_cache,
            }
        )

        # Test
        with config("cache", ratter_cache):
            assert get_import_filepaths(a_cache.filepath) == {"b.py"}
            assert get_import_filepaths(b_cache.filepath) == set()

    def test_get_import_filepaths_circular(self, config):
        """Case of A imports B, B imports A."""
        # Define B
        b_ctx = Context(None)
        b_lib_func = Func("lib_func", ["a"], None, None)
        b_ctx.add_all([
            Name("I_AM_A_CONSTANT"),
            Name("I_AM_JUST_SHOUTING"),
            b_lib_func,
        ])
        b_ir = FileIR(b_ctx)
        b_ir._file_ir = {
            b_lib_func: {
                "sets": {
                    Name("a.attr", "a"),
                },
                "gets": set(),
                "dels": set(),
                "calls": set(),
            }
        }
        b_cache = FileCache(
            filepath="b.py",
            filehash="H(b.py)",
            ir=b_ir,
        )

        # Define A
        # Import B.lib_func
        a_ctx = Context(None)
        import_lib_func = Import("lib_func", "b.lib_func", "b")
        import_lib_func.module_spec = mocked_module_spec("b.py")
        a_func = Func("a_needs_a_fn_too", ["arg"], None, None)
        a_ctx.add_all([
            import_lib_func,
            Name("var_a"),
            Name("var_b"),
            a_func,
        ])
        a_ir = FileIR(a_ctx)
        a_ir._file_ir = {
            a_func: {
                "sets": set(),
                "gets": {
                    Name("arg.something", "arg"),
                },
                "dels": set(),
                "calls": {
                    Call("lib_func()", ["arg"], {}, target=import_lib_func),
                },
            }
        }
        a_cache = FileCache(
            filepath="a.py",
            filehash="H(a.py)",
            ir=a_ir,
        )

        # B imports A
        import_a = Import("a", None, "a")
        import_a.module_spec = mocked_module_spec("a.py")
        b_ctx.add(import_a)

        # New RatterCache
        ratter_cache = RatterCache(
            changed={a_cache.filepath, b_cache.filepath},
            cache_by_file={
                a_cache.filepath: a_cache,
                b_cache.filepath: b_cache,
            }
        )

        # Test
        with config("cache", ratter_cache):
            assert get_import_filepaths(a_cache.filepath) == {"b.py"}
            assert get_import_filepaths(b_cache.filepath) == {"a.py"}

    def test_get_import_filepaths_chained(self, config):
        """Case of A imports B, B imports C."""
        # Define C
        # C holds just data, should still work!
        c_ctx = Context(None)
        c_ctx.add_all([
            Name("state"),
            Name("IMPORTANT_CONSTANT"),
        ])
        c_ir = FileIR(c_ctx)
        c_ir._file_ir = dict()
        c_cache = FileCache(
            filepath="c.py",
            filehash="H(c.py)",
            ir=c_ir,
        )

        # Define B
        b_ctx = Context(None)
        import_constant = Import("IMPORTANT_CONSTANT", "c.IMPORTANT_CONSTANT", "c")
        import_constant.module_spec = mocked_module_spec("c.py")
        b_lib_func = Func("lib_func", ["a"], None, None)
        b_ctx.add_all([
            import_constant,
            Name("I_AM_A_CONSTANT"),
            Name("I_AM_JUST_SHOUTING"),
            b_lib_func,
        ])
        b_ir = FileIR(b_ctx)
        b_ir._file_ir = {
            b_lib_func: {
                "sets": {
                    Name("a.attr", "a"),
                },
                "gets": set(),
                "dels": set(),
                "calls": set(),
            }
        }
        b_cache = FileCache(
            filepath="b.py",
            filehash="H(b.py)",
            ir=b_ir,
        )

        # Define A
        # Import B.lib_func
        a_ctx = Context(None)
        import_lib_func = Import("lib_func", "b.lib_func", "b")
        import_lib_func.module_spec = mocked_module_spec("b.py")
        a_func = Func("a_needs_a_fn_too", ["arg"], None, None)
        a_ctx.add_all([
            import_lib_func,
            Name("var_a"),
            Name("var_b"),
            a_func,
        ])
        a_ir = FileIR(a_ctx)
        a_ir._file_ir = {
            a_func: {
                "sets": set(),
                "gets": {
                    Name("arg.something", "arg"),
                },
                "dels": set(),
                "calls": {
                    Call("lib_func()", ["arg"], {}, target=import_lib_func),
                },
            }
        }
        a_cache = FileCache(
            filepath="a.py",
            filehash="H(a.py)",
            ir=a_ir,
        )

        # New RatterCache
        ratter_cache = RatterCache(
            changed={a_cache.filepath, b_cache.filepath},
            cache_by_file={
                a_cache.filepath: a_cache,
                b_cache.filepath: b_cache,
                c_cache.filepath: c_cache,
            }
        )

        # Test
        with config("cache", ratter_cache):
            assert get_import_filepaths(a_cache.filepath) == {"b.py", "c.py"}
            assert get_import_filepaths(b_cache.filepath) == {"c.py"}
            assert get_import_filepaths(c_cache.filepath) == set()

    def test_get_import_filepaths_circular_chained(self, config):
        """Case of A imports B, B imports C, C imports A."""
        # Define C
        # C holds just data, should still work!
        c_ctx = Context(None)
        c_ctx.add_all([
            Name("state"),
            Name("IMPORTANT_CONSTANT"),
        ])
        c_ir = FileIR(c_ctx)
        c_ir._file_ir = dict()
        c_cache = FileCache(
            filepath="c.py",
            filehash="H(c.py)",
            ir=c_ir,
        )

        # Define B
        b_ctx = Context(None)
        import_constant = Import("IMPORTANT_CONSTANT", "c.IMPORTANT_CONSTANT", "c")
        import_constant.module_spec = mocked_module_spec("c.py")
        b_lib_func = Func("lib_func", ["a"], None, None)
        b_ctx.add_all([
            import_constant,
            Name("I_AM_A_CONSTANT"),
            Name("I_AM_JUST_SHOUTING"),
            b_lib_func,
        ])
        b_ir = FileIR(b_ctx)
        b_ir._file_ir = {
            b_lib_func: {
                "sets": {
                    Name("a.attr", "a"),
                },
                "gets": set(),
                "dels": set(),
                "calls": set(),
            }
        }
        b_cache = FileCache(
            filepath="b.py",
            filehash="H(b.py)",
            ir=b_ir,
        )

        # Define A
        # Import B.lib_func
        a_ctx = Context(None)
        import_lib_func = Import("lib_func", "b.lib_func", "b")
        import_lib_func.module_spec = mocked_module_spec("b.py")
        a_func = Func("a_needs_a_fn_too", ["arg"], None, None)
        a_ctx.add_all([
            import_lib_func,
            Name("var_a"),
            Name("var_b"),
            a_func,
        ])
        a_ir = FileIR(a_ctx)
        a_ir._file_ir = {
            a_func: {
                "sets": set(),
                "gets": {
                    Name("arg.something", "arg"),
                },
                "dels": set(),
                "calls": {
                    Call("lib_func()", ["arg"], {}, target=import_lib_func),
                },
            }
        }
        a_cache = FileCache(
            filepath="a.py",
            filehash="H(a.py)",
            ir=a_ir,
        )

        # C imports A
        import_a = Import("a", None, "a")
        import_a.module_spec = mocked_module_spec("a.py")
        c_ctx.add(import_a)

        # New RatterCache
        ratter_cache = RatterCache(
            changed={a_cache.filepath, b_cache.filepath},
            cache_by_file={
                a_cache.filepath: a_cache,
                b_cache.filepath: b_cache,
                c_cache.filepath: c_cache,
            }
        )

        # Test
        with config("cache", ratter_cache):
            assert get_import_filepaths(a_cache.filepath) == {"b.py", "c.py"}
            assert get_import_filepaths(b_cache.filepath) == {"c.py", "a.py"}
            assert get_import_filepaths(c_cache.filepath) == {"a.py", "b.py"}

    def test__get_direct_imports(self):
        from ratter import config

        # Do not cache
        for file in DO_NOT_CACHE:
            assert _get_direct_imports(file) == list()

        # File not in cache
        assert _get_direct_imports("i-am-not-in-the-cache") == list()

        # Cache IR is unset i.e. cache is initialised but not populated
        unpopulated = config.cache.new("unpopulated.py")
        with pytest.raises(ValueError):
            _get_direct_imports(unpopulated.filepath)

        # Populated, no imports
        context = Context(None)
        populated = config.cache.new("populated.py")
        populated.ir = FileIR(context)
        assert _get_direct_imports(populated.filepath) == list()

        # Populated, w/ imports
        imports = [
            # Stdlib
            Import("pathlib"),
            # Pip
            Import("flask"),
            # Local, ratter
            Import("ratter.cache.cache"),
            # Local, imaginary
            Import("my.special.module"),
        ]
        non_imports = [
            Name("some.redherring.names", "some"),
            Name("that.should.be.wellformed", "that"),
            Name("alpha"),
            Name("beta"),
            Name("gamma"),
            Func("delta", ["a", "b"], None, None),
        ]
        context.add_all(imports)
        context.add_all(non_imports)

        populated.ir = FileIR(context)
        assert _get_direct_imports(populated.filepath) == imports
