from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from rattr.analyser.types import ImportIrs
from rattr.config._types import FollowImports
from rattr.models.ir import FileIr
from rattr.models.results import FileResults
from rattr.models.results.util import (
    cache_is_valid,
    make_arguments_hash,
    make_cacheable_import_info,
    make_cacheable_results,
    make_plugins_hash,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable
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


def test_make_arguments_hash_on_basic_config(mock_config: MakeConfigFn):
    with mock_config(follow_imports=FollowImports(0)):
        assert make_arguments_hash() == "f2fbe32ff21f2a3109277cbdd548466c"


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


def test_make_plugins_hash_on_basic_config(mock_config: MakeConfigFn):
    with mock_config(plugins_blacklist_patterns=()):
        assert make_plugins_hash() == "21bcd105e76db40d7ac76e36900c98b8"


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


def test_cache_is_valid():
    raise NotImplementedError()
