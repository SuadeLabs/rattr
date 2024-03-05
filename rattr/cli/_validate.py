from __future__ import annotations

from typing import TYPE_CHECKING

from rattr import error

if TYPE_CHECKING:
    from typing import NoReturn

    from rattr.config._types import Arguments


def validate_arguments(arguments: Arguments) -> Arguments | NoReturn:
    if arguments._follow_imports_level == 0:
        error.rattr("follow imports not set, results likely to be incomplete")

    if arguments.is_strict and arguments.threshold != 0:
        error.rattr("rattr is in --strict mode, ignoring threshold")

    if arguments.threshold < 0:
        error.fatal("threshold must be a positive integer")

    if not arguments.target.is_file():
        error.fatal(f"file {str(arguments.target)!r} does not exist")

    if arguments.target.suffix != ".py":
        error.rattr(
            f"rattr target expects '*.py', got {str(arguments.target)!r}; "
            f"did you specify the right target?"
        )

    return arguments
