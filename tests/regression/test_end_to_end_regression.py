"""End-to-end regression tests.

NOTE
====
Dues to slight differences in the representation of constants the Python AST between
Python 3.7 and Python 3.8, this test is limited to Python 3,8 plus (for example, it the
output contains a local number this would be `@Num` in one version and `@Constant` in
another, though there is no semantic difference).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from rattr.analyser.file import parse_and_analyse_file
from rattr.analyser.results import ResultsEncoder, generate_results_from_ir
from rattr.analyser.types import FileResults, FunctionResults
from rattr.cli import parse_arguments
from rattr.config import Config

if TYPE_CHECKING:
    from typing import Any, Dict, List, Set

here = Path(__file__).resolve().parent

code_dir = here / "code"
results_dir = here / "results"

code_files = [f for f in code_dir.rglob("*.py")]
results_files = [
    (results_dir / f.relative_to(code_dir)).with_suffix(".json") for f in code_files
]


def _assert_actual_and_expected_have_the_same_functions(
    actual: FileResults,
    expected: Dict[str, Any],
) -> None:
    _actual_results_functions = set(actual.keys())
    _expected_results_functions = set(expected.keys())

    _missing_actual = list(_expected_results_functions - _actual_results_functions)
    _missing_expected = list(_actual_results_functions - _expected_results_functions)

    assert not _missing_actual, f"actual results missing functions: {_missing_actual}"
    assert (
        not _missing_expected
    ), f"expected results missing functions: {_missing_expected}"


def _get_diff(got: Set[str], expected: Set[str]) -> List[str]:
    diff: Set[str] = set()

    for missing in expected - got:
        diff.add(f"- {missing}")

    for missing in got - expected:
        diff.add(f"+ {missing}")

    return list(diff)


def _get_function_diffs(
    fn_results: FunctionResults,
    expected_fn_results: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    return {
        k: _get_diff(fn_results[k], set(expected_fn_results[k]))
        for k in ("sets", "gets", "dels", "calls")
    }


class TestEndToEndRegressionTests:
    def test_e2e_test_data_loaded_correctly(self):
        assert len(code_files) >= 1

        _missing_code_files = [f for f in code_files if not f.is_file()]
        assert not _missing_code_files, "Missing " + ", ".join(
            str(f) for f in _missing_code_files
        )

        assert len(results_files) >= 1

        _missing_result_files = [f for f in results_files if not f.is_file()]
        assert not _missing_result_files, "Missing " + ", ".join(
            str(f) for f in _missing_result_files
        )

    @pytest.mark.py_3_8_plus()
    @pytest.mark.parametrize(
        ("code_file,results_file"),
        zip(code_files, results_files),
        ids=[str(f.relative_to(code_dir)) for f in code_files],
    )
    def test_run_e2e_regression_tests(
        self,
        set_testing_config,
        code_file: Path,
        results_file: Path,
    ):
        # TODO
        #   Make this more end-to-end-y (that is, use `main(...))
        #   This should suffice for now as `main(...)` is not particularly practical for
        #   this test at present, but will be shortly, at which point we can make a
        #   small refactor here.

        # Parse expected results
        expected_results: Dict[str, Any] = json.loads(results_file.read_text())

        # Setup simulated cli arguments and state
        config = Config()
        config.arguments = parse_arguments(
            sys_args=[
                "-w",
                "none",
                "--threshold",
                "0",
                "-o",
                "results",
                str(code_file),
            ],
        )

        # Equivalent to main function
        file_ir, imports_ir, _ = parse_and_analyse_file()
        actual_results = generate_results_from_ir(file_ir, imports_ir)

        if not actual_results:
            pytest.skip(f"no results for {code_file}")

        # Assert unordered (semantic) equality
        _assert_actual_and_expected_have_the_same_functions(
            actual_results, expected_results
        )

        full_file_diff = {
            fn: _get_function_diffs(fn_results, expected_results[fn])
            for fn, fn_results in actual_results.items()
        }

        diff_is_empty = all(
            diff == []
            for _, fn_diffs in full_file_diff.items()
            for _, diff in fn_diffs.items()
        )
        diff_error = (
            f"actual and expected results have the following diff:\n"
            f"{json.dumps(full_file_diff, indent=4)}"
        )

        assert diff_is_empty, diff_error

    @pytest.mark.update_expected_results
    @pytest.mark.parametrize(
        ("code_file,results_file"),
        zip(code_files, results_files),
        ids=[str(f.relative_to(code_dir)) for f in code_files],
    )
    def test_update_expected_results(self, code_file, results_file):
        _cli_arguments = ["-w", "all", "--permissive", "0", "-r"]

        # Setup simulated cli arguments and state
        config = Config()
        config.arguments = parse_arguments([*_cli_arguments, str(code_file)])

        file_ir, imports_ir, _ = parse_and_analyse_file()
        results = generate_results_from_ir(file_ir, imports_ir)

        results_file.write_text(json.dumps(results, indent=4, cls=ResultsEncoder))
