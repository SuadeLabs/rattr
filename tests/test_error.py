from unittest import mock

from rattr import error
from rattr.analyser.util import enter_file


class TestError:
    def test_warning(self, capfd):
        with mock.patch("sys.exit") as _exit:
            error.warning("culprit doesn't matter")

        output, _ = capfd.readouterr()

        assert "warning" in output
        assert not _exit.called

    def test_error(self, capfd):
        with mock.patch("sys.exit") as _exit:
            error.error("culprit doesn't matter")

        output, _ = capfd.readouterr()

        assert "error" in output
        assert not _exit.called

    def test_fatal(self, capfd):
        with mock.patch("sys.exit") as _exit:
            error.fatal("culprit doesn't matter")

        output, _ = capfd.readouterr()

        assert "fatal" in output
        assert _exit.called and _exit.call_count == 1


class TestError_Util:
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
        line_info = "\033[1mline {}:{}: \033[0m".format(
            culprit.lineno, culprit.col_offset
        )
        file_info = "\033[1m{}: \033[0m".format(file)

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

    def test_split_path(self):
        tests = {
            "": [""],
            # Absolute
            "/": [""],
            "/a": ["", "a"],
            "/a/b": ["", "a", "b"],
            "/a/b/c": ["", "a", "b", "c"],
            # Relative
            ".": ["."],
            # Relative, implicit
            "a": [".", "a"],
            "a/b": [".", "a", "b"],
            "a/b/c": [".", "a", "b", "c"],
            # Relative, explicit
            "./a": [".", "a"],
            "./a/b": [".", "a", "b"],
            "./a/b/c": [".", "a", "b", "c"],
            # Relative to home
            "~": ["~"],
            "~/a": ["~", "a"],
            "~/a/b": ["~", "a", "b"],
            "~/a/b/c": ["~", "a", "b", "c"],
        }

        for test_case, expected in tests.items():
            assert error.split_path(test_case) == expected

    def test_format_path(self):
        assert error.format_path(None) is None
        assert error.format_path("") == ""

        short_paths = [
            "/i/am/short",
            "i/am/short",
            "./i/am/short",
            "~/i/am/short",
        ]

        for path, expected in zip(short_paths, short_paths):
            assert error.format_path(path) == expected

        long_paths = {
            "/fill/fill/fill/i/am/a/long/path": "/.../a/long/path",
            "fill/fill/fill/i/am/a/long/path": "./.../a/long/path",
            "./fill/fill/fill/i/am/a/long/path": "./.../a/long/path",
            "~/fill/fill/fill/i/am/a/long/path": "~/.../a/long/path",
        }

        for path, expected in long_paths.items():
            assert error.format_path(path) == expected
