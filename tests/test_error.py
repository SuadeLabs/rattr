from __future__ import annotations

from unittest import mock

import pytest

from rattr import error
from rattr.config.state import enter_file


class TestError:
    def test_warning(self, capfd):
        with mock.patch("sys.exit") as _exit:
            error.warning("culprit doesn't matter")

        _, stderr = capfd.readouterr()

        assert "warning" in stderr
        assert not _exit.called

    def test_error(self, capfd):
        with mock.patch("sys.exit") as _exit:
            error.error("culprit doesn't matter")

        _, stderr = capfd.readouterr()

        assert "error" in stderr
        assert not _exit.called

    def test_fatal(self, capfd):
        with mock.patch("sys.exit") as _exit:
            error.fatal("culprit doesn't matter")

        _, stderr = capfd.readouterr()

        assert "fatal" in stderr
        assert _exit.called and _exit.call_count == 1


class TestErrorUtil:
    def test_get_file_and_line_info(self, parse):
        _ast = parse(
            """
            # not on line 1!
            # not line 2,
            x = 4
            # but third time's the charm
        """
        )
        culprit = _ast.body[0]

        file = "some_file_name.py"
        line_info = "\033[1m:{}:{}\033[0m".format(culprit.lineno, culprit.col_offset)
        file_info = "\033[1m{}\033[0m".format(file)

        # No file, no culprit
        # No file, w/ culprit
        with enter_file(None):
            assert error.get_file_and_line_info(None) == ("", "")
            assert error.get_file_and_line_info(culprit) == ("", line_info)

        # File, no culprit
        # File, w/ culprit
        with enter_file(file):
            assert error.get_file_and_line_info(None) == ("", "")
            assert error.get_file_and_line_info(culprit) == (file_info, line_info)


class TestSplitPath:
    def test_the_empty_string(self):
        assert error.split_path("") == [""]

    @pytest.mark.parametrize(
        "path,parts",
        testcases := [
            ("/", [""]),
            ("/a", ["", "a"]),
            ("/a/b", ["", "a", "b"]),
            ("/a/b/c", ["", "a", "b", "c"]),
        ],
        ids=[t[0] for t in testcases],
    )
    def test_absolute_path(self, path, parts):
        assert error.split_path(path) == parts

    @pytest.mark.parametrize("path,parts", ts := [(".", ["."])], ids=[t[0] for t in ts])
    def test_relative_to_this_dir(self, path, parts):
        assert error.split_path(path) == parts

    @pytest.mark.parametrize(
        "path,parts",
        testcases := [
            ("a", [".", "a"]),
            ("a/b", [".", "a", "b"]),
            ("a/b/c", [".", "a", "b", "c"]),
        ],
        ids=[t[0] for t in testcases],
    )
    def test_relative_implicit(self, path, parts):
        assert error.split_path(path) == parts

    @pytest.mark.parametrize(
        "path,parts",
        testcases := [
            ("./a", [".", "a"]),
            ("./a/b", [".", "a", "b"]),
            ("./a/b/c", [".", "a", "b", "c"]),
        ],
        ids=[t[0] for t in testcases],
    )
    def test_relative_explicit(self, path, parts):
        assert error.split_path(path) == parts

    @pytest.mark.parametrize(
        "path,parts",
        testcases := [
            ("~", ["~"]),
            ("~/a", ["~", "a"]),
            ("~/a/b", ["~", "a", "b"]),
            ("~/a/b/c", ["~", "a", "b", "c"]),
        ],
        ids=[t[0] for t in testcases],
    )
    def test_path_is_in_home(self, path, parts):
        assert error.split_path(path) == parts


class TestFormatPath:
    def test_null_path(self):
        assert error.format_path(None) is None

    def test_the_empty_string(self):
        assert error.format_path("") == ""

    @pytest.mark.parametrize(
        "raw,formatted",
        testcases := [
            ("/i/am/short", "/i/am/short"),
            ("i/am/short", "i/am/short"),
            ("./i/am/short", "./i/am/short"),
            ("~/i/am/short", "~/i/am/short"),
        ],
        ids=[t[0] for t in testcases],
    )
    def test_short_path(self, config, raw, formatted):
        with config("use_short_path", True):
            assert error.format_path(raw) == formatted

    @pytest.mark.parametrize(
        "raw,formatted",
        testcases := [
            ("/a/very/deeply/nested/path/gt/than/8/parts/long", "/.../8/parts/long"),
            ("a/very/deeply/nested/path/gt/than/8/parts/long", "./.../8/parts/long"),
            ("./a/very/deeply/nested/path/gt/than/8/parts/long", "./.../8/parts/long"),
            ("~/a/very/deeply/nested/path/gt/than/8/parts/long", "~/.../8/parts/long"),
        ],
        ids=[t[0] for t in testcases],
    )
    def test_long_path(self, config, raw, formatted):
        with config("use_short_path", True):
            assert error.format_path(raw) == formatted
