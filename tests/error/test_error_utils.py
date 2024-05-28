from __future__ import annotations

from typing import TYPE_CHECKING

from rattr import error
from rattr.config.state import enter_file

if TYPE_CHECKING:
    import ast


class TestErrorUtils:
    def test_get_file_and_line_info(self, parse):
        ast_module: ast.Module = parse(
            """
            # not on line 1!
            # not line 2,
            x = 4
            # but third time's the charm
            """
        )
        culprit: ast.expr = ast_module.body[0]

        line_info = "\033[1m:{}:{}\033[0m".format(culprit.lineno, culprit.col_offset)

        # No file, no culprit
        # No file, w/ culprit
        with enter_file(None):
            file_info = "\033[1m{}\033[0m".format("target.py")
            assert error.get_file_and_line_info(None) == (file_info, "")
            assert error.get_file_and_line_info(culprit) == (file_info, line_info)

        # File, no culprit
        # File, w/ culprit
        with enter_file(file := "some_file_name.py"):
            file_info = "\033[1m{}\033[0m".format(file)
            assert error.get_file_and_line_info(None) == (file_info, "")
            assert error.get_file_and_line_info(culprit) == (file_info, line_info)
