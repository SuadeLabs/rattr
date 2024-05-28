from __future__ import annotations

import sys
from functools import partial
from pathlib import Path

import pytest

short_relative_path = Path("relative_dir") / "file.txt"
long_relative_path = (
    Path("relative_dir")
    / "with"
    / "some"
    / "deeply"
    / "nested"
    / "content"
    / "inside.it"
)


short_absolute_path_in_home = Path.home().resolve() / "rattr" / "target.py"
long_absolute_path_in_home = (
    Path.home().resolve()
    / "some"
    / "deeply"
    / "nested"
    / "path"
    / "to"
    / "some"
    / "rattr"
    / "target.py"
)


short_absolute_path_not_in_home = Path("/tmp") / "my_temp.file"
long_absolute_path_not_in_home = (
    Path("/tmp") / "a" / "b" / "c" / "dee" / "eff" / "jee" / "my_temp.file"
)

short_absolute_path_not_in_home_windows = Path("C:/") / "Program Files" / "thefile.win"
long_absolute_path_not_in_home_windows = (
    Path("C:/")
    / "Program Files"
    / "Rattr"
    / "Config"
    / "Made Up"
    / "Path"
    / "Here"
    / "thefile.win"
)


@pytest.fixture
def reset(state):
    return partial(
        state,
        badness_from_simplification=0,
        badness_from_target_file=0,
        badness_from_imports=0,
    )


@pytest.fixture
def assert_badness(config):
    def _make_assertion(simplification: int, target: int, imports: int):
        assert config.state.badness_from_simplification == simplification
        assert config.state.badness_from_target_file == target
        assert config.state.badness_from_imports == imports

    return _make_assertion


@pytest.fixture
def badness(state):
    def _set_badness(simplification: int, target: int, imports: int):
        return state(
            badness_from_simplification=simplification,
            badness_from_target_file=target,
            badness_from_imports=imports,
        )

    return _set_badness


class TestState:
    def test_badness_vs_full_badness(self, badness, config):
        # For now at least these are expected to differ, thus there should be a test
        # for regression purposes at the very least.
        with badness(simplification=3, target=5, imports=7):
            assert config.state.badness == 8
            assert config.state.full_badness == 15


class TestConfig:
    def test_increment_badness(self, assert_badness, config, state, reset):
        with reset():
            assert_badness(simplification=0, target=0, imports=0)

            with state(current_file=None):
                config.increment_badness(5)

            assert_badness(simplification=5, target=0, imports=0)

        with reset():
            assert_badness(simplification=0, target=0, imports=0)

            with state(current_file=Path("target.py")):
                config.increment_badness(5)

            assert_badness(simplification=0, target=5, imports=0)

        with reset():
            assert_badness(simplification=0, target=0, imports=0)

            with state(current_file="not none but not the target"):
                config.increment_badness(5)

            assert_badness(simplification=0, target=0, imports=5)

    def test_is_within_badness_threshold_is_strict(self, config, arguments, badness):
        with arguments(is_strict=True):
            with badness(simplification=0, target=0, imports=0):
                assert config.is_within_badness_threshold

            with badness(simplification=1, target=0, imports=0):
                assert not config.is_within_badness_threshold

            with badness(simplification=0, target=1, imports=0):
                assert not config.is_within_badness_threshold

            with badness(simplification=0, target=0, imports=1):
                assert config.is_within_badness_threshold

    def test_is_within_badness_threshold_infinite_threshold(
        self, config, arguments, badness
    ):
        with arguments(is_strict=False, threshold=0):
            with badness(simplification=0, target=0, imports=0):
                assert config.is_within_badness_threshold

            with badness(simplification=1_000, target=0, imports=0):
                assert config.is_within_badness_threshold

            with badness(simplification=0, target=1_000, imports=0):
                assert config.is_within_badness_threshold

            with badness(simplification=0, target=0, imports=1_000):
                assert config.is_within_badness_threshold

    def test_is_within_badness_threshold_ordinary(self, config, arguments, badness):
        with arguments(is_strict=False, threshold=500):
            with badness(simplification=0, target=0, imports=0):
                assert config.is_within_badness_threshold

            # Simplification badness is part of badness
            with badness(simplification=499, target=0, imports=0):
                assert config.is_within_badness_threshold
            with badness(simplification=500, target=0, imports=0):
                assert config.is_within_badness_threshold
            with badness(simplification=501, target=0, imports=0):
                assert not config.is_within_badness_threshold

            # Target file badness is part of badness
            with badness(simplification=0, target=499, imports=0):
                assert config.is_within_badness_threshold
            with badness(simplification=0, target=500, imports=0):
                assert config.is_within_badness_threshold
            with badness(simplification=0, target=501, imports=0):
                assert not config.is_within_badness_threshold

            # Imported badness is *not* part of badness (only full_badness)
            with badness(simplification=0, target=0, imports=499):
                assert config.is_within_badness_threshold
            with badness(simplification=0, target=0, imports=500):
                assert config.is_within_badness_threshold
            with badness(simplification=0, target=0, imports=501):
                assert config.is_within_badness_threshold

            with badness(simplification=250, target=250, imports=101):
                assert config.is_within_badness_threshold
            with badness(simplification=251, target=250, imports=101):
                assert not config.is_within_badness_threshold

    def test_formatted_current_file_path(self, config, arguments, state):
        file = Path.home() / "this" / "is" / "a" / "path" / "to" / "a.file"

        with arguments(collapse_home=True, truncate_deep_paths=True):
            with state(current_file=None):
                assert config.formatted_current_file_path is None

            with state(current_file=file):
                assert config.formatted_current_file_path == "~/.../path/to/a.file"

    def test_formatted_target_path(self, config, arguments):
        file = Path.home() / "this" / "is" / "a" / "path" / "to" / "a.file"

        with arguments(collapse_home=True, truncate_deep_paths=True):
            with arguments(target=None):
                assert config.formatted_target_path is None

            with arguments(target=file):
                assert config.formatted_target_path == "~/.../path/to/a.file"


class TestGetFormattedPath:
    def test_path_is_none(self, config):
        assert config.get_formatted_path(None) is None

    @pytest.mark.parametrize(
        "path,expected",
        [
            (short_relative_path, short_relative_path.as_posix()),
            (long_relative_path, long_relative_path.as_posix()),
            (short_absolute_path_in_home, short_absolute_path_in_home.as_posix()),
            (long_absolute_path_in_home, long_absolute_path_in_home.as_posix()),
            (
                short_absolute_path_not_in_home,
                short_absolute_path_not_in_home.as_posix(),
            ),
            (long_absolute_path_not_in_home, long_absolute_path_not_in_home.as_posix()),
        ],
        ids=[
            "short_relative_path",
            "long_relative_path",
            "short_absolute_path_in_home",
            "long_absolute_path_in_home",
            "short_absolute_path_not_in_home",
            "long_absolute_path_not_in_home",
        ],
    )
    def test_raw_path(self, config, arguments, path, expected):
        with arguments(collapse_home=False, truncate_deep_paths=False):
            assert config.get_formatted_path(path) == expected

    @pytest.mark.parametrize(
        "path,expected",
        [
            (short_relative_path, short_relative_path.as_posix()),
            (long_relative_path, long_relative_path.as_posix()),
            (short_absolute_path_in_home, "~/rattr/target.py"),
            (
                long_absolute_path_in_home,
                "~/some/deeply/nested/path/to/some/rattr/target.py",
            ),
            (
                short_absolute_path_not_in_home,
                short_absolute_path_not_in_home.as_posix(),
            ),
            (long_absolute_path_not_in_home, long_absolute_path_not_in_home.as_posix()),
        ],
        ids=[
            "short_relative_path",
            "long_relative_path",
            "short_absolute_path_in_home",
            "long_absolute_path_in_home",
            "short_absolute_path_not_in_home",
            "long_absolute_path_not_in_home",
        ],
    )
    def test_collapsed_home(self, config, arguments, path, expected):
        with arguments(collapse_home=True, truncate_deep_paths=False):
            assert config.get_formatted_path(path) == expected

    @pytest.mark.parametrize(
        "path,expected",
        [
            (short_relative_path, short_relative_path.as_posix()),
            (long_relative_path, "relative_dir/.../nested/content/inside.it"),
            (short_absolute_path_in_home, short_absolute_path_in_home.as_posix()),
            (long_absolute_path_in_home, "/.../some/rattr/target.py"),
            (
                short_absolute_path_not_in_home,
                short_absolute_path_not_in_home.as_posix(),
            ),
            (long_absolute_path_not_in_home, "/.../eff/jee/my_temp.file"),
        ],
        ids=[
            "short_relative_path",
            "long_relative_path",
            "short_absolute_path_in_home",
            "long_absolute_path_in_home",
            "short_absolute_path_not_in_home",
            "long_absolute_path_not_in_home",
        ],
    )
    def test_truncate_deep_paths(self, config, arguments, path, expected):
        if path == long_absolute_path_in_home and sys.platform == "win32":
            expected = f"C:{expected}"

        with arguments(collapse_home=False, truncate_deep_paths=True):
            assert config.get_formatted_path(path) == expected

    @pytest.mark.parametrize(
        "path,expected",
        [
            (short_relative_path, short_relative_path.as_posix()),
            (long_relative_path, "relative_dir/.../nested/content/inside.it"),
            (short_absolute_path_in_home, "~/rattr/target.py"),
            (long_absolute_path_in_home, "~/.../some/rattr/target.py"),
            (
                short_absolute_path_not_in_home,
                short_absolute_path_not_in_home.as_posix(),
            ),
            (long_absolute_path_not_in_home, "/.../eff/jee/my_temp.file"),
        ],
        ids=[
            "short_relative_path",
            "long_relative_path",
            "short_absolute_path_in_home",
            "long_absolute_path_in_home",
            "short_absolute_path_not_in_home",
            "long_absolute_path_not_in_home",
        ],
    )
    def test_fully_formatted(self, config, arguments, path, expected):
        with arguments(collapse_home=True, truncate_deep_paths=True):
            assert config.get_formatted_path(path) == expected

    @pytest.mark.windows
    def test_windows(self, config, arguments):
        with arguments(collapse_home=False, truncate_deep_paths=False):
            assert (
                config.get_formatted_path(short_absolute_path_not_in_home_windows)
                == "C:/Program Files/thefile.win"
            )
            assert (
                config.get_formatted_path(long_absolute_path_not_in_home_windows)
                == "C:/Program Files/Rattr/Config/Made Up/Path/Here/thefile.win"
            )

        with arguments(collapse_home=False, truncate_deep_paths=True):
            assert (
                config.get_formatted_path(short_absolute_path_not_in_home_windows)
                == "C:/Program Files/thefile.win"
            )
            assert (
                config.get_formatted_path(long_absolute_path_not_in_home_windows)
                == "C:/.../Path/Here/thefile.win"
            )

        with arguments(collapse_home=True, truncate_deep_paths=False):
            assert (
                config.get_formatted_path(short_absolute_path_not_in_home_windows)
                == "C:/Program Files/thefile.win"
            )
            assert (
                config.get_formatted_path(long_absolute_path_not_in_home_windows)
                == "C:/Program Files/Rattr/Config/Made Up/Path/Here/thefile.win"
            )

        with arguments(collapse_home=True, truncate_deep_paths=True):
            assert (
                config.get_formatted_path(short_absolute_path_not_in_home_windows)
                == "C:/Program Files/thefile.win"
            )
            assert (
                config.get_formatted_path(long_absolute_path_not_in_home_windows)
                == "C:/.../Path/Here/thefile.win"
            )
