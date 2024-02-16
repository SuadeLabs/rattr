from __future__ import annotations

from rattr import error
from rattr.config.state import enter_file


class TestErrorUtils:
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
        file_info = "\033[1m{}\033[0m".format(file)
        line_info = "\033[1m:{}:{}\033[0m".format(culprit.lineno, culprit.col_offset)

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
