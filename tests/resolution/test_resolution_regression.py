from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

import tests.helpers as helpers
from rattr.analyser.file import parse_and_analyse_file
from rattr.cli import parse_arguments
from rattr.config import Config
from rattr.results import generate_results_from_ir

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest import CaptureFixture


here = Path(__file__).resolve().parent


@contextmanager
def set_cwd(new_working_dir: Path | str) -> Generator[None]:
    old_working_dir = os.getcwd()
    os.chdir(new_working_dir)

    with mock.patch(
        "rattr.module_locator._locate.derive_working_dir",
        new=lambda: str(new_working_dir),
    ):
        yield

    os.chdir(old_working_dir)


def test_do_not_give_warning_on_call_to_method_on_imported_member(
    capfd: CaptureFixture[str],
):
    config = Config()
    config.arguments = parse_arguments(
        sys_args=[
            "--collapse-home",
            *("--warning", "all"),
            *("--stdout", "silent"),
            *("--threshold", "0"),
            str(here / "code" / "target.py"),
        ],
    )

    # Equivalent to main function
    with set_cwd(here / "code"):
        file_ir, import_irs, _ = parse_and_analyse_file()
        _ = generate_results_from_ir(target_ir=file_ir, import_irs=import_irs)

    # This was a two part fix.
    #
    # Firstly
    # -------
    # On finding the target for a call to a member of an imported target we now check
    # that the imported symbol (which will always be an `Import`) actually refers to a
    # module, if it does not we likely imported variable, etc and so should not follow
    # the call as it is a method call.
    #
    # This fixed the following error:
    #   error: tests/resolution/code/module/util.py:3:0: unable to resolve call to 'get'
    #   in import 'module.constants', it is likely undefined
    #
    #
    # Secondly
    # --------
    # When unable to resolve the target because it is a method on a non-module imported
    # member, do not give the warning that the target is undefined (as it is not
    # undefined but rather unresolvable and there are too many hits for this warning to
    # be useful).
    #
    # Given the first fixed is applied, this gave the following warning:
    #   warning: tests/resolution/code/module/util.py:7:11: unable to resolve call to
    #   'CONSTANT.get()', target is undefined

    # Before fixing, this would give the following error:
    # unable to resolve call to 'get' in import 'module.constants', it is likely undefined
    _, stderr = capfd.readouterr()
    assert helpers.stderr_matches(stderr, [])
