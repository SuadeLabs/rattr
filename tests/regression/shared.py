from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rattr.models.ir import FileIr
from rattr.models.results import FileResults, FunctionResults

if TYPE_CHECKING:
    from typing import Any


here = Path(__file__).resolve().parent

code_dir = here / "code"
results_dir = here / "results"
irs_dir = here / "irs"

code_files = [f for f in code_dir.rglob("*.py")]
results_files = [
    (results_dir / code_file.relative_to(code_dir)).with_suffix(".json")
    for code_file in code_files
]
ir_files = [
    (irs_dir / code_file.relative_to(code_dir)).with_suffix(".json")
    for code_file in code_files
]


def assert_actual_and_expected_have_the_same_functions_results(
    actual: FileResults,
    expected: dict[str, Any],
) -> None:
    actual_results_functions = set(actual.keys())
    expected_results_functions = set(expected.keys())

    missing_actual = list(expected_results_functions - actual_results_functions)
    missing_expected = list(actual_results_functions - expected_results_functions)

    assert not missing_actual, f"actual results missing functions: {missing_actual}"
    assert (
        not missing_expected
    ), f"expected results missing functions: {missing_expected}"


def assert_actual_and_expected_have_the_same_functions_irs(
    actual: FileIr,
    expected: FileIr,
) -> None:
    actual_results_functions = set(actual.keys())
    expected_results_functions = set(expected.keys())

    missing_actual = list(expected_results_functions - actual_results_functions)
    missing_expected = list(actual_results_functions - expected_results_functions)

    assert not missing_actual, f"actual results missing functions: {missing_actual}"
    assert (
        not missing_expected
    ), f"expected results missing functions: {missing_expected}"


def results_diff(got: set[str], expected: set[str]) -> list[str]:
    diff: set[str] = set()

    for missing in expected - got:
        diff.add(f"- {missing}")

    for missing in got - expected:
        diff.add(f"+ {missing}")

    return list(diff)


def results_function_diffs(
    fn_results: FunctionResults,
    expected_fn_results: dict[str, list[str]],
) -> dict[str, list[str]]:
    return {
        k: results_diff(fn_results[k], set(expected_fn_results[k]))
        for k in ("sets", "gets", "dels", "calls")
    }
