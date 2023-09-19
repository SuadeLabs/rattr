"""Run the full analyser (in single file mode) on a snippet of code.

This should test source code snippets containing the use of a single feature, to ensure
that when run through the full analyser the end results and IR are as expected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rattr.analyser.context.symbol import Builtin, Call, Func, Name, Symbol

if TYPE_CHECKING:
    from typing import Callable

    from rattr.analyser.context import Context
    from rattr.analyser.types import FileIR, FileResults


class TestGeneratorExpression:
    def test_simple_generator_expression(
        self,
        analyse_single_file: Callable[[str], tuple[FileIR, FileResults]],
        root_context_with: Callable[[list[Symbol]], Context],
    ):
        file_ir, file_results = analyse_single_file(
            """
            def sum_attrs(xs):
                return sum(x.attr for x in xs)
            """
        )

        symbols = {
            "sum": Builtin("sum", has_affect=False),
            "sum_attrs": Func("sum_attrs", ["xs"]),
        }

        assert file_ir.context == root_context_with(symbols.values())
        assert file_ir._file_ir == {
            symbols["sum_attrs"]: {
                "gets": {
                    Name("x"),
                    Name("xs"),
                    Name("x.attr", "x"),
                },
                "sets": set(),
                "dels": set(),
                "calls": {
                    Call("sum()", ["@GeneratorExp"], {}, target=symbols["sum"]),
                },
            }
        }
        assert file_results == {
            "sum_attrs": {
                "gets": {"xs", "x", "x.attr"},
                "sets": set(),
                "dels": set(),
                "calls": {"sum()"},
            }
        }
