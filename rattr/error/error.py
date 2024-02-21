"""Rattr error/logging functions."""
from __future__ import annotations

import ast
import sys
from enum import Enum
from typing import NoReturn

from rattr.config import Config, ShowWarnings
from rattr.models.symbol import Symbol

__ERROR = "{prefix}: {optional_file_info}{optional_line_info}: {message}"
__FILE_INFO = "\033[1m{}\033[0m"
__LINE_INFO = "\033[1m:{}:{}\033[0m"


# --------------------------------------------------------------------------- #
# Rattr errors
# --------------------------------------------------------------------------- #


class Level(Enum):
    rattr = "\033[34;1mrattr\033[0m"  # Blue
    info = "\033[33;1minfo\033[0m"  # Yellow / Orange
    warning = "\033[33;1mwarning\033[0m"  # Yellow / Orange
    error = "\033[31;1merror\033[0m"  # Red
    fatal = "\033[31;1mfatal\033[0m"  # Red


def rattr(
    message: str,
    culprit: ast.AST | Symbol | None = None,
    badness: int = 0,
) -> None:
    """Log a message with the prefix "rattr", not for analyser errors."""
    __log(Level.rattr, message, culprit)


def info(
    message: str,
    culprit: ast.AST | Symbol | None = None,
    badness: int = 0,
) -> None:
    """Log a low-priority warning and, if given, include culprit info."""
    config = Config()
    config.increment_badness(badness)

    if config.do_not_show_warnings:
        return

    if config.is_in_target_file:
        warning_level = ShowWarnings.target_low_priority
    else:
        warning_level = ShowWarnings.inherited_low_priority

    if warning_level not in config.arguments.show_warnings:
        return

    __log(Level.info, message, culprit)


def warning(
    message: str,
    culprit: ast.AST | Symbol | None = None,
    badness: int = 1,
) -> None:
    """Log a warning and, if given, include culprit line and file info."""
    config = Config()
    config.increment_badness(badness)

    if config.do_not_show_warnings:
        return

    if config.is_in_target_file:
        warning_level = ShowWarnings.target
    else:
        warning_level = ShowWarnings.inherited_high_priority

    if warning_level not in config.arguments.show_warnings:
        return

    __log(Level.warning, message, culprit)


def error(
    message: str,
    culprit: ast.AST | Symbol | None = None,
    badness: int = 5,
) -> None:
    """Log an error and, if given, include culprit line and file info."""
    config = Config()
    config.increment_badness(badness)

    if badness > 0 and config.arguments.is_strict:
        fatal(message, culprit)

    __log(Level.error, message, culprit)


def fatal(
    message: str,
    culprit: ast.AST | Symbol | None = None,
    badness: int = 0,  # noqa
) -> NoReturn:
    """Log a fatal error and, if given, include culprit line and file info.

    NOTE
        A fatal error has no notion of badness as it will always cause an
        immediate EXIT_FAILURE, however, badness is provided in the function
        interface for consistency with the other errors.

        Regardless of the provided badness value, a badness of 0 will be used.

    """
    config = Config()
    config.increment_badness(badness)

    __log(Level.fatal, message, culprit)

    sys.exit(1)


def get_file_and_line_info(culprit: ast.AST | Symbol | None) -> tuple[str, str]:
    """Return the formatted line and line and file info as strings."""
    config = Config()

    if culprit is None:
        return "", ""

    if isinstance(culprit, Symbol):
        if (location := culprit.location) is not None:
            file_info = __FILE_INFO.format(config.get_formatted_path(location.file))
        else:
            file_info = __file_info_from_config()
    else:
        file_info = __file_info_from_config()

    if isinstance(culprit, Symbol):
        if (token := culprit.token) is not None:
            line_info = __LINE_INFO.format(token.lineno, token.col_offset)
        else:
            line_info = ""
    else:
        line_info = __LINE_INFO.format(culprit.lineno, culprit.col_offset)

    return file_info, line_info


def __file_info_from_config() -> str:
    config = Config()

    if config.formatted_current_file_path:
        file_info = __FILE_INFO.format(config.formatted_current_file_path)
    else:
        file_info = ""

    return file_info


def __log(
    level: Level,
    message: str,
    culprit: ast.AST | Symbol | None = None,
) -> None:
    file_info, line_info = get_file_and_line_info(culprit)

    print(
        __ERROR.format(
            prefix=level.value,
            optional_file_info=file_info,
            optional_line_info=line_info,
            message=message,
        ),
        file=sys.stderr,
    )
