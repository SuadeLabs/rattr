from __future__ import annotations

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
    def test_badness_vs_full_badness(self):
        # For now at least these are expected to differ, thus there should be a test
        # for regression purposes at the very least.
        raise AssertionError


class TestConfig:
    def test_root_cache_dir(self):
        raise AssertionError

    def test_increment_badness(self):
        raise AssertionError

    def test_is_within_badness_threshold(self):
        raise AssertionError

    def test_formatted_current_file_path(self):
        raise AssertionError

    def formatted_target_path(self):
        raise AssertionError


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
