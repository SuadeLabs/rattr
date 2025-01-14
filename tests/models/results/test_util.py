from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from rattr.analyser.types import ImportIrs
from rattr.config._types import FollowImports
from rattr.models.ir import FileIr
from rattr.models.results import CacheableResults, FileResults
from rattr.models.results.util import (
    make_arguments_hash,
    make_cacheable_import_info,
    make_cacheable_results,
    make_plugins_hash,
    target_cache_file_is_up_to_date,
)
from rattr.models.symbol import Import, Location
from rattr.models.util import serialise

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable
    from contextlib import AbstractContextManager
    from typing import Any, Protocol

    from tests.shared import MakeRootContextFn

    class Mocked(Protocol):
        def __enter__(self):
            ...

        def __exit__(self, *_):
            ...

    class MakeConfigFn(Protocol):
        def __call__(
            self,
            *,
            literal_value_prefix: str = "@",
            plugins_blacklist_patterns: Iterable[str] = (),
            follow_imports: FollowImports = FollowImports.pip,
            excluded_imports: Iterable[str] = (),
            excluded_names: Iterable[str] = (),
        ) -> Mocked:
            ...

    class WriteTempCacheFileFn(Protocol):
        def __call__(
            self,
            cache: CacheableResults,
            /,
        ) -> AbstractContextManager[Path]:
            ...


@pytest.fixture()
def mock_config():
    @contextmanager
    def factory(
        *,
        literal_value_prefix: str = "@",
        plugins_blacklist_patterns: Iterable[str] = (),
        follow_imports: FollowImports = FollowImports.pip,
        excluded_imports: Iterable[str] = (),
        excluded_names: Iterable[str] = (),
    ) -> Generator[None]:
        with mock.patch("rattr.models.results.util.Config") as m_config:
            m_config.return_value = mock.Mock(
                LITERAL_VALUE_PREFIX=literal_value_prefix,
                PLUGINS_BLACKLIST_PATTERNS=set(plugins_blacklist_patterns),
                arguments=mock.Mock(
                    follow_imports=follow_imports,
                    excluded_imports=set(excluded_imports),
                    excluded_names=set(excluded_names),
                ),
            )
            yield

    return factory


@pytest.fixture()
def write_temp_cache_file():
    @contextmanager
    def factory(cache: CacheableResults, /) -> Generator[Path, None, None]:
        with tempfile.NamedTemporaryFile("w", delete=False) as fp:
            filepath = fp.name
            fp.write(serialise(cache, indent=4))

        yield Path(fp.name)

        os.unlink(filepath)

    return factory


@pytest.mark.posix
def test_make_arguments_hash_on_basic_config(mock_config: MakeConfigFn):
    with mock_config(follow_imports=FollowImports(0)):
        assert make_arguments_hash() == "f2fbe32ff21f2a3109277cbdd548466c"


@pytest.mark.posix
@pytest.mark.parametrize(
    "initial_kwargs, initial_hash, changed_kwargs, changed_hash",
    [
        (
            {"literal_value_prefix": "@"},
            "15ac5025e41407a0620de4dbb896fe7b",
            {"literal_value_prefix": "#"},
            "be743fdc22d027549bf8d418d5fb2949",
        ),
        (
            {"follow_imports": FollowImports(0)},
            "f2fbe32ff21f2a3109277cbdd548466c",
            {"follow_imports": FollowImports.pip | FollowImports.local},
            "170fd6c97d06ab37e4e09ddf6f8cd372",
        ),
        # Exclude imports
        (
            {"excluded_imports": ()},
            "15ac5025e41407a0620de4dbb896fe7b",
            {"excluded_imports": ("blah",)},
            "b95b0f5413efb4c7f102344c13b93b6e",
        ),
        (
            {"excluded_imports": ("bla",)},
            "74d4b6d37234f9f0b9fe3cf183daccad",
            {"excluded_imports": ("blah",)},
            "b95b0f5413efb4c7f102344c13b93b6e",
        ),
        (
            {"excluded_imports": ()},
            "15ac5025e41407a0620de4dbb896fe7b",
            {"excluded_imports": ("blah", "bla")},
            "09e324d546299d7ccbcc46a18b996240",
        ),
        (
            {"excluded_imports": ("bla",)},
            "74d4b6d37234f9f0b9fe3cf183daccad",
            {"excluded_imports": ("blah", "bla")},
            "09e324d546299d7ccbcc46a18b996240",
        ),
        # Exclude names
        (
            {"excluded_names": ()},
            "15ac5025e41407a0620de4dbb896fe7b",
            {"excluded_names": ("blah",)},
            "aa5009b3cf4e468eeb75756fdf6b9873",
        ),
        (
            {"excluded_names": ("bla",)},
            "a6a2e5ca55bf075eaf318b9ca60e1291",
            {"excluded_names": ("blah",)},
            "aa5009b3cf4e468eeb75756fdf6b9873",
        ),
        (
            {"excluded_names": ()},
            "15ac5025e41407a0620de4dbb896fe7b",
            {"excluded_names": ("blah", "bla")},
            "013455ff0d8e3c1e775aa6646faa9474",
        ),
        (
            {"excluded_names": ("bla",)},
            "a6a2e5ca55bf075eaf318b9ca60e1291",
            {"excluded_names": ("blah", "bla")},
            "013455ff0d8e3c1e775aa6646faa9474",
        ),
    ],
    ids=[
        "literal_value_prefix",
        "follow_imports",
        "exclude_imports_case_a",
        "exclude_imports_case_b",
        "exclude_imports_case_c",
        "exclude_imports_case_d",
        "exclude_names_case_a",
        "exclude_names_case_b",
        "exclude_names_case_c",
        "exclude_names_case_d",
    ],
)
def test_make_arguments_hash_changes_on_arguments_change(
    mock_config: MakeConfigFn,
    initial_kwargs: dict[str, Any],
    initial_hash: str,
    changed_kwargs: dict[str, Any],
    changed_hash: str,
):
    with mock_config(**initial_kwargs):
        assert (initial := make_arguments_hash()) == initial_hash

    with mock_config(**changed_kwargs):
        assert (changed := make_arguments_hash()) == changed_hash

    assert initial != changed


@pytest.mark.posix
@pytest.mark.parametrize(
    "initial_kwargs, changed_kwargs, expected_hash",
    [
        (
            {"excluded_imports": ("blah",)},
            {"excluded_imports": ("blah", "blah")},
            "b95b0f5413efb4c7f102344c13b93b6e",
        ),
        (
            {"excluded_names": ("bla", "blah")},
            {"excluded_names": ("blah", "bla", "blah")},
            "013455ff0d8e3c1e775aa6646faa9474",
        ),
    ],
    ids=["excluded_imports", "excluded_names"],
)
def test_make_arguments_hash_changes_on_semantic_equivalence(
    mock_config: MakeConfigFn,
    initial_kwargs: dict[str, Any],
    changed_kwargs: dict[str, Any],
    expected_hash: str,
):
    with mock_config(**initial_kwargs):
        assert (initial := make_arguments_hash()) == expected_hash

    with mock_config(**changed_kwargs):
        assert (changed := make_arguments_hash()) == expected_hash

    assert initial == changed


@pytest.mark.posix
def test_make_plugins_hash_on_basic_config(mock_config: MakeConfigFn):
    with mock_config(plugins_blacklist_patterns=()):
        assert make_plugins_hash() == "21bcd105e76db40d7ac76e36900c98b8"


@pytest.mark.posix
@pytest.mark.parametrize(
    "initial_kwargs, initial_hash, changed_kwargs, changed_hash",
    [
        (
            {"plugins_blacklist_patterns": ()},
            "21bcd105e76db40d7ac76e36900c98b8",
            {"plugins_blacklist_patterns": ("blah",)},
            "be7ef7ee0e5281b021d1293c2370be6b",
        ),
        (
            {"plugins_blacklist_patterns": ("bla",)},
            "ce2fdc9b04c52dca5b173a4bceddadee",
            {"plugins_blacklist_patterns": ("blah",)},
            "be7ef7ee0e5281b021d1293c2370be6b",
        ),
        (
            {"plugins_blacklist_patterns": ("blah",)},
            "be7ef7ee0e5281b021d1293c2370be6b",
            {"plugins_blacklist_patterns": ("blah", "bla")},
            "ebd3cd30b3cc078727ec56dab419e47d",
        ),
    ],
    ids=[
        "plugins_blacklist_patterns_case_a",
        "plugins_blacklist_patterns_case_b",
        "plugins_blacklist_patterns_case_c",
    ],
)
def test_make_plugins_hash_changes_on_arguments_change(
    mock_config: MakeConfigFn,
    initial_kwargs: dict[str, Any],
    initial_hash: str,
    changed_kwargs: dict[str, Any],
    changed_hash: str,
):
    with mock_config(**initial_kwargs):
        assert (initial := make_plugins_hash()) == initial_hash

    with mock_config(**changed_kwargs):
        assert (changed := make_plugins_hash()) == changed_hash

    assert initial != changed


@pytest.mark.posix
@pytest.mark.parametrize(
    "initial_kwargs, changed_kwargs, expected_hash",
    [
        (
            {"plugins_blacklist_patterns": ("blah",)},
            {"plugins_blacklist_patterns": ("blah", "blah")},
            "be7ef7ee0e5281b021d1293c2370be6b",
        ),
        (
            {"plugins_blacklist_patterns": ("bla", "blah")},
            {"plugins_blacklist_patterns": ("blah", "bla", "blah")},
            "ebd3cd30b3cc078727ec56dab419e47d",
        ),
    ],
    ids=["plugins_blacklist_patterns_case_a", "plugins_blacklist_patterns_case_b"],
)
def test_make_plugins_hash_changes_on_semantic_equivalence(
    mock_config: MakeConfigFn,
    initial_kwargs: dict[str, Any],
    changed_kwargs: dict[str, Any],
    expected_hash: str,
):
    with mock_config(**initial_kwargs):
        assert (initial := make_plugins_hash()) == expected_hash

    with mock_config(**changed_kwargs):
        assert (changed := make_plugins_hash()) == expected_hash

    assert initial == changed


@pytest.mark.posix
def test_make_cacheable_results_basic_coverage(
    mock_config: MakeConfigFn,
    make_root_context: MakeRootContextFn,
):
    # Does not error
    with mock_config():
        make_cacheable_results(
            FileResults(),
            FileIr(context=make_root_context((), include_root_symbols=True)),
            ImportIrs(),
        )


@pytest.mark.posix
def test_make_cacheable_results_equality(
    mock_config: MakeConfigFn,
    make_root_context: MakeRootContextFn,
):
    with mock_config():
        lhs = make_cacheable_results(
            FileResults(),
            FileIr(context=make_root_context((), include_root_symbols=True)),
            ImportIrs(),
        )
        rhs = make_cacheable_results(
            FileResults(),
            FileIr(context=make_root_context((), include_root_symbols=True)),
            ImportIrs(),
        )

    assert lhs == rhs


@pytest.mark.posix
def test_make_cacheable_results_inequality(
    mock_config: MakeConfigFn,
    make_root_context: MakeRootContextFn,
):
    with mock_config():
        lhs = make_cacheable_results(
            FileResults(),
            FileIr(context=make_root_context((), include_root_symbols=True)),
            ImportIrs(),
        )
    with mock_config(excluded_imports=["something"]):
        rhs = make_cacheable_results(
            FileResults(),
            FileIr(context=make_root_context((), include_root_symbols=True)),
            ImportIrs(),
        )

    assert lhs != rhs


@pytest.mark.posix
def test_make_cacheable_import_info_basic_coverage(
    mock_config: MakeConfigFn,
    make_root_context: MakeRootContextFn,
):
    # Does not error
    with mock_config():
        make_cacheable_import_info(
            FileIr(context=make_root_context((), include_root_symbols=True)),
            ImportIrs(),
        )


@pytest.mark.posix
@mock.patch("rattr.models.results.util.isfile", lambda _: True)  # type: ignore[reportUnknownArgumentType]
def test_target_cache_file_is_up_to_date_basic_coverage(
    mock_config: MakeConfigFn,
    make_root_context: MakeRootContextFn,
    write_temp_cache_file: WriteTempCacheFileFn,
):
    with mock_config():
        cache = make_cacheable_results(
            FileResults(),
            FileIr(context=make_root_context((), include_root_symbols=True)),
            ImportIrs(),
        )

        with write_temp_cache_file(cache) as file:
            assert target_cache_file_is_up_to_date(cache.filepath, file)


@pytest.mark.posix
@mock.patch("rattr.models.results.util.isfile", lambda _: True)  # type: ignore[reportUnknownArgumentType]
def test_target_cache_file_is_up_to_date_basic_coverage_with_import(
    mock_config: MakeConfigFn,
    make_root_context: MakeRootContextFn,
    write_temp_cache_file: WriteTempCacheFileFn,
):
    with mock_config(), tempfile.NamedTemporaryFile(mode="w") as fp:
        fake_import_filepath = fp.name
        fp.write("blah")

        # Create fake imported file
        import_symbol = Import(
            "thing",
            "thing",
            location=Location(1, 1, 1, 1, file=Path(fake_import_filepath)),
        )
        import_name_and_spec = ("thing", mock.Mock(origin=fake_import_filepath))

        with mock.patch(
            "rattr.models.symbol._symbols.find_module_name_and_spec",
            lambda _: import_name_and_spec,  # type: ignore[reportUnknownArgumentType]
        ):
            cache = make_cacheable_results(
                FileResults(),
                FileIr(context=make_root_context([import_symbol])),
                ImportIrs(),  # Only needed for imports in import
            )

            with write_temp_cache_file(cache) as file:
                assert target_cache_file_is_up_to_date(cache.filepath, file)


@pytest.mark.posix
@mock.patch("rattr.models.results.util.isfile", lambda _: True)  # type: ignore[reportUnknownArgumentType]
def test_target_cache_file_is_up_to_date_changed_version(
    mock_config: MakeConfigFn,
    make_root_context: MakeRootContextFn,
    write_temp_cache_file: WriteTempCacheFileFn,
):
    with mock_config():
        with mock.patch("rattr.models.results.util.version", "0.1.8"):
            cache = make_cacheable_results(
                FileResults(),
                FileIr(context=make_root_context((), include_root_symbols=True)),
                ImportIrs(),
            )

        with mock.patch("rattr.models.results.util.version", "0.2.0"):
            with write_temp_cache_file(cache) as file:
                assert not target_cache_file_is_up_to_date(cache.filepath, file)


@pytest.mark.posix
@mock.patch("rattr.models.results.util.isfile", lambda _: True)  # type: ignore[reportUnknownArgumentType]
def test_target_cache_file_is_up_to_date_changed_target_file(
    mock_config: MakeConfigFn,
    make_root_context: MakeRootContextFn,
    write_temp_cache_file: WriteTempCacheFileFn,
):
    with mock_config():
        cache = make_cacheable_results(
            FileResults(),
            FileIr(context=make_root_context((), include_root_symbols=True)),
            ImportIrs(),
        )

        with write_temp_cache_file(cache) as file:
            assert not target_cache_file_is_up_to_date(Path("not_test.py"), file)


@pytest.mark.posix
@mock.patch("rattr.models.results.util.isfile", lambda _: True)  # type: ignore[reportUnknownArgumentType]
def test_target_cache_file_is_up_to_date_changed_target_filehash(
    mock_config: MakeConfigFn,
    make_root_context: MakeRootContextFn,
    write_temp_cache_file: WriteTempCacheFileFn,
):
    with mock_config():
        with tempfile.NamedTemporaryFile(mode="w") as fp:
            filepath = fp.name

            # Initial file content and cache
            fp.write("blah")
            target = FileIr(context=make_root_context((), include_root_symbols=True))
            target.context._file = Path(filepath)  # type: ignore[reportPrivateUsage]
            cache = make_cacheable_results(FileResults(), target, ImportIrs())

            # File content updated and thus cache is invalid
            fp.seek(0)
            fp.write("blah\nblah")
            with write_temp_cache_file(cache) as file:
                assert not target_cache_file_is_up_to_date(cache.filepath, file)


@pytest.mark.posix
@mock.patch("rattr.models.results.util.isfile", lambda _: True)  # type: ignore[reportUnknownArgumentType]
def test_target_cache_file_is_up_to_date_changed_arguments(
    mock_config: MakeConfigFn,
    make_root_context: MakeRootContextFn,
    write_temp_cache_file: WriteTempCacheFileFn,
):
    with mock_config(follow_imports=FollowImports.local):
        cache = make_cacheable_results(
            FileResults(),
            FileIr(context=make_root_context((), include_root_symbols=True)),
            ImportIrs(),
        )

    with mock_config(follow_imports=FollowImports.local | FollowImports.pip):
        with write_temp_cache_file(cache) as file:
            assert not target_cache_file_is_up_to_date(cache.filepath, file)


@pytest.mark.posix
@mock.patch("rattr.models.results.util.isfile", lambda _: True)  # type: ignore[reportUnknownArgumentType]
def test_target_cache_file_is_up_to_date_changed_plugins(
    mock_config: MakeConfigFn,
    make_root_context: MakeRootContextFn,
    write_temp_cache_file: WriteTempCacheFileFn,
):
    with mock_config(plugins_blacklist_patterns=("foo",)):
        cache = make_cacheable_results(
            FileResults(),
            FileIr(context=make_root_context((), include_root_symbols=True)),
            ImportIrs(),
        )

    with mock_config(plugins_blacklist_patterns=("foo", "bar")):
        with write_temp_cache_file(cache) as file:
            assert not target_cache_file_is_up_to_date(cache.filepath, file)


@pytest.mark.posix
@mock.patch("rattr.models.results.util.isfile", lambda _: True)  # type: ignore[reportUnknownArgumentType]
def test_target_cache_file_is_up_to_date_changed_import_hash(
    mock_config: MakeConfigFn,
    make_root_context: MakeRootContextFn,
    write_temp_cache_file: WriteTempCacheFileFn,
):
    with mock_config(), tempfile.NamedTemporaryFile(mode="w") as fp:
        fake_import_filepath = fp.name

        # Create fake imported file
        import_symbol = Import(
            "thing",
            "thing",
            location=Location(1, 1, 1, 1, file=Path(fake_import_filepath)),
        )
        import_name_and_spec = ("thing", mock.Mock(origin=fake_import_filepath))

        with mock.patch(
            "rattr.models.symbol._symbols.find_module_name_and_spec",
            lambda _: import_name_and_spec,  # type: ignore[reportUnknownArgumentType]
        ):
            # Initial file content and cache
            fp.write("blah")
            cache = make_cacheable_results(
                FileResults(),
                FileIr(context=make_root_context([import_symbol])),
                ImportIrs(),
            )

            # File content updated and thus cache is invalid
            fp.seek(0)
            fp.write("blah\nblah")
            with write_temp_cache_file(cache) as file:
                assert not target_cache_file_is_up_to_date(cache.filepath, file)


@pytest.mark.posix
def test_target_cache_file_is_up_to_date_non_existant_target():
    assert not target_cache_file_is_up_to_date(Path("test.py"), __file__)


@pytest.mark.posix
def test_target_cache_file_is_up_to_date_non_existant_cache_file():
    assert not target_cache_file_is_up_to_date(__file__, Path("no_such_file.json"))


@pytest.mark.posix
@mock.patch("rattr.models.results.util.isfile", lambda _: True)  # type: ignore[reportUnknownArgumentType]
def test_target_cache_file_is_up_to_date_deserialisation_error():
    with tempfile.NamedTemporaryFile(mode="w") as fp:
        fp.write("blah")
        filename = fp.name
        assert not target_cache_file_is_up_to_date(Path("test.py"), filename)
