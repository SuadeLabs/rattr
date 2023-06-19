from __future__ import annotations

from pathlib import Path
from unittest import mock

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

short_absolute_path_not_in_home_windows = Path("C:\\") / "Program Files" / "thefile.win"
long_absolute_path_not_in_home_windows = (
    Path("C:\\")
    / "Program Files"
    / "Rattr"
    / "Config"
    / "Made Up"
    / "Path"
    / "Here"
    / "thefile.win"
)


class TestState:
    def test_badness_vs_full_badness(self, config, state):
        # For now at least these are expected to differ, thus there should be a test
        # for regression purposes at the very least.
        with state(
            badness_from_target_file=3,
            badness_from_imports=5,
            badness_from_simplification=7,
        ):
            assert config.state.badness == 10
            assert config.state.full_badness == 15


class TestConfig:
    @mock.patch("rattr.config._types.find_project_root")
    def test_root_cache_dir(self, m_find_project_root, config):
        project_root = Path("~") / "my_project"
        m_find_project_root.return_value = project_root

        assert config.root_cache_dir == project_root / ".rattr" / "cache"

    def test_increment_badness(self, config, state):
        assert config.state.badness_from_simplification == 0
        assert config.state.badness_from_target_file == 0
        assert config.state.badness_from_imports == 0

        with state(current_file=None):
            config.increment_badness(5)
        assert config.state.badness_from_simplification == 5
        assert config.state.badness_from_target_file == 0
        assert config.state.badness_from_imports == 0

        with state(current_file=Path("target.py")):
            config.increment_badness(5)
        assert config.state.badness_from_simplification == 5
        assert config.state.badness_from_target_file == 5
        assert config.state.badness_from_imports == 0

        with state(current_file="not none but not the target"):
            config.increment_badness(5)
        assert config.state.badness_from_simplification == 5
        assert config.state.badness_from_target_file == 5
        assert config.state.badness_from_imports == 5

    def test_is_within_badness_threshold_is_strict(self, config, arguments, state):
        with arguments(is_strict=True):
            with state(
                badness_from_simplification=0,
                badness_from_target_file=0,
                badness_from_imports=0,
            ):
                assert config.is_within_badness_threshold

            with state(
                badness_from_simplification=1,
                badness_from_target_file=0,
                badness_from_imports=0,
            ):
                assert not config.is_within_badness_threshold

            with state(
                badness_from_simplification=0,
                badness_from_target_file=1,
                badness_from_imports=0,
            ):
                assert not config.is_within_badness_threshold

            with state(
                badness_from_simplification=0,
                badness_from_target_file=0,
                badness_from_imports=1,
            ):
                assert config.is_within_badness_threshold

    def test_is_within_badness_threshold_infinite_threshold(self, config, arguments, state):
        with arguments(is_strict=False, threshold=0):
            with state(
                badness_from_simplification=0,
                badness_from_target_file=0,
                badness_from_imports=0,
            ):
                assert config.is_within_badness_threshold

            with state(
                badness_from_simplification=1_000,
                badness_from_target_file=0,
                badness_from_imports=0,
            ):
                assert config.is_within_badness_threshold

            with state(
                badness_from_simplification=0,
                badness_from_target_file=1_000,
                badness_from_imports=0,
            ):
                assert config.is_within_badness_threshold

            with state(
                badness_from_simplification=0,
                badness_from_target_file=0,
                badness_from_imports=1_000,
            ):
                assert config.is_within_badness_threshold

    def test_is_within_badness_threshold_ordinary(self, config, arguments, state):
        with arguments(is_strict=False, threshold=500):
            with state(
                badness_from_simplification=0,
                badness_from_target_file=0,
                badness_from_imports=0,
            ):
                assert config.is_within_badness_threshold

            with state(
                badness_from_simplification=499,
                badness_from_target_file=0,
                badness_from_imports=0,
            ):
                assert config.is_within_badness_threshold
            with state(
                badness_from_simplification=500,
                badness_from_target_file=0,
                badness_from_imports=0,
            ):
                assert config.is_within_badness_threshold
            with state(
                badness_from_simplification=501,
                badness_from_target_file=0,
                badness_from_imports=0,
            ):
                assert not config.is_within_badness_threshold

            with state(
                badness_from_simplification=0,
                badness_from_target_file=499,
                badness_from_imports=0,
            ):
                assert config.is_within_badness_threshold
            with state(
                badness_from_simplification=0,
                badness_from_target_file=500,
                badness_from_imports=0,
            ):
                assert config.is_within_badness_threshold
            with state(
                badness_from_simplification=0,
                badness_from_target_file=501,
                badness_from_imports=0,
            ):
                assert not config.is_within_badness_threshold

            with state(
                badness_from_simplification=0,
                badness_from_target_file=0,
                badness_from_imports=499,
            ):
                assert config.is_within_badness_threshold
            with state(
                badness_from_simplification=0,
                badness_from_target_file=0,
                badness_from_imports=500,
            ):
                assert config.is_within_badness_threshold
            with state(
                badness_from_simplification=0,
                badness_from_target_file=0,
                badness_from_imports=501,
            ):
                assert config.is_within_badness_threshold

            with state(
                badness_from_simplification=250,
                badness_from_target_file=250,
                badness_from_imports=101,
            ):
                assert config.is_within_badness_threshold
            with state(
                badness_from_simplification=251,
                badness_from_target_file=250,
                badness_from_imports=101,
            ):
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
            (short_relative_path, str(short_relative_path)),
            (long_relative_path, str(long_relative_path)),
            (short_absolute_path_in_home, str(short_absolute_path_in_home)),
            (long_absolute_path_in_home, str(long_absolute_path_in_home)),
            (short_absolute_path_not_in_home, str(short_absolute_path_not_in_home)),
            (long_absolute_path_not_in_home, str(long_absolute_path_not_in_home)),
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
            (short_relative_path, str(short_relative_path)),
            (long_relative_path, str(long_relative_path)),
            (short_absolute_path_in_home, "~/rattr/target.py"),
            (
                long_absolute_path_in_home,
                "~/some/deeply/nested/path/to/some/rattr/target.py",
            ),
            (short_absolute_path_not_in_home, str(short_absolute_path_not_in_home)),
            (long_absolute_path_not_in_home, str(long_absolute_path_not_in_home)),
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
            (short_relative_path, str(short_relative_path)),
            (long_relative_path, "relative_dir/.../nested/content/inside.it"),
            (short_absolute_path_in_home, str(short_absolute_path_in_home)),
            (long_absolute_path_in_home, "/.../some/rattr/target.py"),
            (short_absolute_path_not_in_home, str(short_absolute_path_not_in_home)),
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
        with arguments(collapse_home=False, truncate_deep_paths=True):
            assert config.get_formatted_path(path) == expected

    @pytest.mark.parametrize(
        "path,expected",
        [
            (short_relative_path, str(short_relative_path)),
            (long_relative_path, "relative_dir/.../nested/content/inside.it"),
            (short_absolute_path_in_home, "~/rattr/target.py"),
            (long_absolute_path_in_home, "~/.../some/rattr/target.py"),
            (short_absolute_path_not_in_home, str(short_absolute_path_not_in_home)),
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
                == "C:\\Program Files\\thefile.win"
            )
            assert (
                config.get_formatted_path(long_absolute_path_not_in_home_windows)
                == "C:\\Program Files\\Rattr\\Config\\Made Up\\Path\\Here\\thefile.win"
            )

        with arguments(collapse_home=False, truncate_deep_paths=True):
            assert (
                config.get_formatted_path(short_absolute_path_not_in_home_windows)
                == "C:\\Program Files\\thefile.win"
            )
            assert (
                config.get_formatted_path(long_absolute_path_not_in_home_windows)
                == "C:\\...\\Path\\Here\\thefile.win"
            )

        with arguments(collapse_home=True, truncate_deep_paths=False):
            assert (
                config.get_formatted_path(short_absolute_path_not_in_home_windows)
                == "C:\\Program Files\\thefile.win"
            )
            assert (
                config.get_formatted_path(long_absolute_path_not_in_home_windows)
                == "C:\\Program Files\\Rattr\\Config\\Made Up\\Path\\Here\\thefile.win"
            )

        with arguments(collapse_home=True, truncate_deep_paths=True):
            assert (
                config.get_formatted_path(short_absolute_path_not_in_home_windows)
                == "C:\\Program Files\\thefile.win"
            )
            assert (
                config.get_formatted_path(long_absolute_path_not_in_home_windows)
                == "C:\\...\\Path\\Here\\thefile.win"
            )
