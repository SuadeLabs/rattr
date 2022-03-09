"""Rattr error/logging functions."""

import ast
import sys
from enum import Enum
from os.path import expanduser
from typing import List, Optional, Tuple

from rattr import config

__ERROR = "{prefix}: {optional_file_info}{optional_line_info}{message}"
__FILE_INFO = "\033[1m{}: \033[0m"
__LINE_INFO = "\033[1mline {}:{}: \033[0m"


# --------------------------------------------------------------------------- #
# Rattr errors
# --------------------------------------------------------------------------- #


class Level(Enum):
    RATTR = "\033[34;1mrattr\033[0m"  # Blue
    INFO = "\033[33;1minfo\033[0m"  # Yellow / Orange
    WARNING = "\033[33;1mwarning\033[0m"  # Yellow / Orange
    ERROR = "\033[31;1merror\033[0m"  # Red
    FATAL = "\033[31;1mfatal\033[0m"  # Red


def rattr(
    message: str,
    culprit: Optional[ast.AST] = None,
    badness: int = 0,  # noqa
) -> None:
    """Log a message with the prefix "rattr", not for analyser errors."""
    __log(Level.RATTR, message, culprit)


def info(
    message: str,
    culprit: Optional[ast.AST] = None,
    badness: int = 0,
) -> None:
    """Log a low-priority warning and, if given, include culprit info."""
    __increment_badness(badness)

    if not config.show_warnings:
        return

    if not config.show_low_priority_warnings:
        return

    if not config.show_imports_warnings and config.current_file != config.file:
        return

    __log(Level.INFO, message, culprit)


def warning(
    message: str,
    culprit: Optional[ast.AST] = None,
    badness: int = 1,
) -> None:
    """Log a warning and, if given, include culprit line and file info."""
    __increment_badness(badness)

    if not config.show_warnings:
        return

    if not config.show_imports_warnings and config.current_file != config.file:
        return

    __log(Level.WARNING, message, culprit)


def error(
    message: str,
    culprit: Optional[ast.AST] = None,
    badness: int = 5,
) -> None:
    """Log an error and, if given, include culprit line and file info."""
    __increment_badness(badness)

    if config.strict and badness > 0:
        fatal(message, culprit)

    __log(Level.ERROR, message, culprit)


def fatal(
    message: str,
    culprit: Optional[ast.AST] = None,
    badness: int = 0,  # noqa
) -> None:
    """Log a fatal error and, if given, include culprit line and file info.

    NOTE
        A fatal error has no notion of badness as it will always cause an
        immediate EXIT_FAILURE, however, badness is provided in the function
        interface for consistency with the other errors.

        Regardless of the provided badness value, a badness of 0 will be used.

    """
    __increment_badness(0)

    __log(Level.FATAL, message, culprit)

    sys.exit(1)


def get_badness() -> int:
    """Return the badness value."""
    return config.file_badness + config.simplify_badness


def is_within_badness_threshold() -> bool:
    """Return `True` if the program is within the current badness threshold."""
    badness = get_badness()

    if config.strict:
        return badness <= 0

    # NOTE A threshold of 0 is equivalent to a threshold of ∞
    if config.threshold == 0:
        return True

    return badness <= config.threshold


# --------------------------------------------------------------------------- #
# Raisable errors
# --------------------------------------------------------------------------- #


class RattrUnsupportedError(Exception):
    """Language feature is unsupported by Rattr."""

    pass


class RattrUnaryOpInNameable(TypeError):
    """Unary operation found when resolving name."""

    pass


class RattrBinOpInNameable(TypeError):
    """Binary operation found when resolving name."""

    pass


class RattrConstantInNameable(TypeError):
    """Constant found when resolving name."""

    pass


class RattrLiteralInNameable(TypeError):
    """Literal found when resolving name."""

    pass


class RattrComprehensionInNameable(TypeError):
    """Comprehension found when resolving name."""

    pass


# --------------------------------------------------------------------------- #
# Error utils
# --------------------------------------------------------------------------- #


def get_file_and_line_info(culprit: Optional[ast.AST]) -> Tuple[str, str]:
    """Return the formatted line and line and file info as strings."""
    if culprit is None:
        return "", ""

    if config.current_file is not None and config.show_path:
        file_info = __FILE_INFO.format(format_path(config.current_file))
    else:
        file_info = ""

    line_info = __LINE_INFO.format(culprit.lineno, culprit.col_offset)

    return file_info, line_info


def split_path(path: str) -> List[str]:
    """Return the components of the path.

    >>> path == "/".join(split_path(path))
    True
    for all path

    >>> split_path("a/b/c")
    ["a", "b", "c"]

    >>> split_path("/a/b/c")
    ["", "a", "b", "c"]

    >>> split_path("~/a/b/c")
    ["~", "a", "b", "c"]

    """
    if path in ("", "/"):
        return [""]

    # if path.startswith("/"):
    #     return ["/"] + path[1:].split("/")

    if not path.startswith((".", "~", "/")):
        path = f"./{path}"

    return path.split("/")


def format_path(path: Optional[str]) -> Optional[str]:
    """Return the given path formatted in line with `config`."""
    if path is None:
        return None

    if not config.use_short_path:
        return path

    # Replace $HOME with "~"
    path = path.replace(expanduser("~"), "~")

    # Abbreviate long heirachies
    segments = split_path(path)
    if len(segments) > 5:
        path = "/".join([segments[0], "...", *segments[-3:]])

    return path


def __log(
    level: Level,
    message: str,
    culprit: Optional[ast.AST] = None,
) -> None:
    file_info, line_info = get_file_and_line_info(culprit)

    print(
        __ERROR.format(
            prefix=level.value,
            optional_file_info=file_info,
            optional_line_info=line_info,
            message=message,
        )
    )


def __increment_badness(badness: int) -> None:
    if isinstance(badness, int) and badness < 0:
        raise ValueError("'badness' must be positive integer")

    if config.current_file == config.file:
        config.file_badness += badness
    elif config.current_file is None:
        config.simplify_badness += badness
    else:
        config.import_badness += badness
