from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from functools import partial
from typing import TYPE_CHECKING

import pytest

from rattr.error.error import Level

if TYPE_CHECKING:
    from typing import Final


_ERROR_FORMAT: Final = "{level}: {location}{message}"

_LOCATION: Final = "\033[1mline {line}:{col}: \033[0m"
_LOCATION_PATTERN: Final = r"\033\[1mline {line}:{col}: \033\[0m"


class ReLevel(Enum):
    rattr = r"\033\[34;1mrattr\033\[0m"
    info = r"\033\[33;1minfo\033\[0m"
    warning = r"\033\[33;1mwarning\033\[0m"
    error = r"\033\[31;1merror\033\[0m"
    fatal = r"\033\[31;1mfatal\033\[0m"


@dataclass
class ExpectedError:
    message: str

    level: Level = Level.fatal  # must be kw for partial s.t. message may be pos
    re_level: ReLevel = ReLevel.fatal

    expect_location: bool = True
    line: str = r"\w+"
    col: str = r"\w+"

    def __post_init__(self) -> None:
        # Allow line/col as int
        self.line = str(self.line)
        self.col = str(self.col)

    def matches(self, target: str) -> bool:
        return self.re_expected.fullmatch(target) is not None

    @property
    def re_expected(self) -> re.Pattern[str]:
        if self.expect_location:
            # re_location = f"line {self.line}:{self.col}: "
            re_location = _LOCATION_PATTERN.format(line=self.line, col=self.col)
        else:
            re_location = ""

        pattern = _ERROR_FORMAT.format(
            level=self.re_level.value,
            location=re_location,
            message=self.message,
        )

        return re.compile(pattern)

    def as_debug_output(self) -> str:
        if self.expect_location:
            location = _LOCATION.format(line=self.line, col=self.col)
        else:
            location = ""

        return _ERROR_FORMAT.format(
            level=self.level.value,
            location=location,
            message=self.message,
        )


as_rattr = partial(ExpectedError, level=Level.rattr, re_level=ReLevel.rattr)
as_info = partial(ExpectedError, level=Level.info, re_level=ReLevel.info)
as_warning = partial(ExpectedError, level=Level.warning, re_level=ReLevel.warning)
as_error = partial(ExpectedError, level=Level.error, re_level=ReLevel.error)
as_fatal = partial(ExpectedError, level=Level.fatal, re_level=ReLevel.fatal)


def _pretty_print_output_lines(
    heading: str,
    output_lines: list[str] | list[ExpectedError],
) -> None:
    if len(output_lines) and isinstance(output_lines[0], ExpectedError):
        lines: list[str] = [e.as_debug_output() for e in output_lines]
    else:
        lines: list[str] = output_lines

    print(heading)
    print("-" * len(heading))

    for line in lines:
        print(line)

    print()


def stdout_matches(
    stdout: str | pytest.CaptureFixture[str],
    expected: list[ExpectedError],
    *,
    silent: bool = False,
) -> bool:
    if isinstance(stdout, pytest.CaptureFixture):
        (stdout, _) = stdout.readouterr()

    lines = stdout.splitlines()

    _has_expected_length = len(lines) == len(expected)
    _all_lines_match_expected = all(e.matches(l) for e, l in zip(expected, lines))

    if _has_expected_length and _all_lines_match_expected:
        return True

    # Display expected output for debugging
    # Pytest will already display the actual captured output
    if not silent:
        _pretty_print_output_lines("actual stdout to match:", lines)
        _pretty_print_output_lines(
            "expected stdout as re patterns:",
            [e.as_debug_output() for e in expected],
        )

    return False
