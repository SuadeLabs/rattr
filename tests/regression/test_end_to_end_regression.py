"""End-to-end regression tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from rattr.analyser.file import parse_and_analyse_file
from rattr.cli import parse_arguments
from rattr.config import Config
from rattr.models.util import OutputIrs, deserialise, serialise, serialise_irs
from rattr.results import generate_results_from_ir
from tests.regression.shared import (
    assert_actual_and_expected_have_the_same_functions_irs,
    assert_actual_and_expected_have_the_same_functions_results,
    code_dir,
    code_files,
    ir_files,
    results_files,
    results_function_diffs,
)

if TYPE_CHECKING:
    from typing import Any

    from tests.shared import OsDependentPathFn


# TODO
# Ensure Python path CWD is set correctly.
# See: tests/resolution/test_resolution_regression.py


@pytest.mark.parametrize(
    ("code_file,results_file"),
    zip(code_files, results_files),
    ids=[str(f.relative_to(code_dir)) for f in code_files],
)
def test_run_e2e_regression_tests_for_results(
    code_file: Path,
    results_file: Path,
):
    # TODO
    #   Make this more end-to-end-y (that is, use `main(...))
    #   This should suffice for now as `main(...)` is not particularly practical for
    #   this test at present, but will be shortly, at which point we can make a
    #   small refactor here.

    # Parse expected results
    expected_results: dict[str, Any] = json.loads(results_file.read_text())

    # Setup simulated cli arguments and state
    config = Config()
    config.arguments = parse_arguments(
        sys_args=[
            "--collapse-home",
            *("--warning", "none"),
            *("--threshold", "0"),
            *("--stdout", "results"),
            str(code_file),
        ],
    )

    # Equivalent to main function
    file_ir, import_irs, _ = parse_and_analyse_file()
    actual_results = generate_results_from_ir(target_ir=file_ir, import_irs=import_irs)

    if not actual_results:
        pytest.skip(f"no results for {code_file}")

    # Assert unordered (semantic) equality
    assert_actual_and_expected_have_the_same_functions_results(
        actual_results,
        expected_results,
    )

    full_file_diff = {
        fn: results_function_diffs(fn_results, expected_results[fn])
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
def test_update_expected_results(code_file: Path, results_file: Path):
    # Setup simulated cli arguments and state
    config = Config()
    config.arguments = parse_arguments(
        sys_args=[
            *("--warning", "all"),
            *("--threshold", "0"),
            *("--stdout", "results"),
            str(code_file),
        ]
    )

    file_ir, import_irs, _ = parse_and_analyse_file()
    results = generate_results_from_ir(target_ir=file_ir, import_irs=import_irs)

    results_file.write_text(serialise(results, indent=4))


@pytest.mark.posix
@pytest.mark.cpython
@pytest.mark.python_3_9
@pytest.mark.parametrize(
    ("code_file,ir_file"),
    zip(code_files, ir_files),
    ids=[str(f.relative_to(code_dir)) for f in code_files],
)
def test_run_e2e_regression_tests_for_ir(
    code_file: Path,
    ir_file: Path,
    os_dependent_path: OsDependentPathFn,
):
    # TODO See todo in test_run_e2e_regression_tests_for_results

    # Parse expected results
    expected_irs = deserialise(ir_file.read_text(), type=OutputIrs)

    # Setup simulated cli arguments and state
    config = Config()
    config.arguments = parse_arguments(
        sys_args=[
            "--collapse-home",
            *("--warning", "none"),
            *("--threshold", "0"),
            *("--stdout", "ir"),
            str(code_file),
        ],
    )

    # Equivalent to main function
    file_ir, import_irs, _ = parse_and_analyse_file()
    _ = generate_results_from_ir(target_ir=file_ir, import_irs=import_irs)

    # Ensure filename is the same in CI
    actual_tests_dir = Path(__file__).parents[1]
    expected_tests_dir = Path("/home/suade/rattr/feature/tests")
    filename = expected_tests_dir / code_file.relative_to(actual_tests_dir)

    irs = OutputIrs(
        import_irs=import_irs,
        target_ir={
            "filename": os_dependent_path(str(filename)),
            "ir": file_ir,
        },
    )

    if not file_ir and not import_irs:
        pytest.skip(f"no irs for {code_file}")

    # Assert unordered (semantic) equality
    assert irs.import_irs.keys() == expected_irs.import_irs.keys()
    for mod in irs.import_irs.keys():
        assert_actual_and_expected_have_the_same_functions_irs(
            irs.import_irs[mod],
            expected_irs.import_irs[mod],
        )
    assert_actual_and_expected_have_the_same_functions_irs(
        irs.target_ir["ir"],
        expected_irs.target_ir["ir"],
    )

    assert irs.import_irs == expected_irs.import_irs
    assert irs.target_ir["filename"] == expected_irs.target_ir["filename"]
    assert irs.target_ir["ir"] == expected_irs.target_ir["ir"]


@pytest.mark.update_expected_irs
@pytest.mark.parametrize(
    ("code_file,ir_files"),
    zip(code_files, ir_files),
    ids=[str(f.relative_to(code_dir)) for f in code_files],
)
def test_update_expected_ir(code_file: Path, ir_files: Path):
    # Setup simulated cli arguments and state
    config = Config()
    config.arguments = parse_arguments(
        sys_args=[
            *("--warning", "all"),
            *("--threshold", "0"),
            *("--stdout", "ir"),
            str(code_file),
        ]
    )

    file_ir, import_irs, _ = parse_and_analyse_file()
    _ = generate_results_from_ir(target_ir=file_ir, import_irs=import_irs)

    serialised = serialise_irs(
        target_name=str(code_file),
        target_ir=file_ir,
        import_irs=import_irs,
    )
    ir_files.write_text(serialised)
