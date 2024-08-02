from __future__ import annotations

import inspect
import re
from collections import deque
from dataclasses import dataclass
from enum import Enum
from functools import cache, partial
from typing import TYPE_CHECKING

import pytest

from rattr.error.error import Level

if TYPE_CHECKING:
    import types
    from typing import Final, Literal, Protocol

    class MemoisedFunction(Protocol):
        def cache_clear(self) -> None:
            ...


ERROR_MESSAGE_TEMPLATE: Final = "{level}: {file_info}{line_info}: {message}"

ERROR_FILE_INFO_TEMPLATE: Final = "\033[1m{file}\033[0m"
ERROR_FILE_INFO_ESCAPED: Final = r"\033\[1m{file}\033\[0m"

ERROR_LINE_INFO_TEMPLATE: Final = "\033[1m:{line}:{col}\033[0m"
ERROR_LINE_INFO_ESCAPED: Final = r"\033\[1m:{line}:{col}\033\[0m"


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
    file: str = r"\w+.py"
    line: str = r"\d+"
    col: str = r"\d+"

    def __post_init__(self) -> None:
        # Allow line/col as int
        self.line = str(self.line)
        self.col = str(self.col)

    def matches(self, target: str) -> bool:
        return self.re_expected.fullmatch(target) is not None

    @property
    def re_expected(self) -> re.Pattern[str]:
        if self.expect_location:
            re_file_info = ERROR_FILE_INFO_ESCAPED.format(file=self.file)
            re_line_info = ERROR_LINE_INFO_ESCAPED.format(line=self.line, col=self.col)
        else:
            re_file_info = ""
            re_line_info = ""

        pattern = ERROR_MESSAGE_TEMPLATE.format(
            level=self.re_level.value,
            file_info=re_file_info,
            line_info=re_line_info,
            message=self.message,
        )

        return re.compile(pattern)

    def as_debug_output(self) -> str:
        if self.expect_location:
            file_info = ERROR_FILE_INFO_TEMPLATE.format(file=self.file)
            line_info = ERROR_LINE_INFO_TEMPLATE.format(line=self.line, col=self.col)
        else:
            file_info = ""
            line_info = ""

        return ERROR_MESSAGE_TEMPLATE.format(
            level=self.level.value,
            file_info=file_info,
            line_info=line_info,
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
    return output_matches(stdout, expected, output_type="stdout", silent=silent)


def stderr_matches(
    stderr: str | pytest.CaptureFixture[str],
    expected: list[ExpectedError],
    *,
    silent: bool = False,
) -> bool:
    if isinstance(stderr, pytest.CaptureFixture):
        (_, stderr) = stderr.readouterr()
    return output_matches(stderr, expected, output_type="stderr", silent=silent)


def output_matches(
    output: str | pytest.CaptureFixture[str],
    expected: list[ExpectedError],
    *,
    output_type: Literal["stdout", "stderr"],
    silent: bool = False,
) -> bool:
    if isinstance(output, pytest.CaptureFixture):
        (output, _) = output.readouterr()

    lines = output.splitlines()

    _has_expected_length = len(lines) == len(expected)
    _all_lines_match_expected = all(e.matches(l) for e, l in zip(expected, lines))

    if _has_expected_length and _all_lines_match_expected:
        return True

    # Display expected output for debugging
    # Pytest will already display the actual captured output
    if not silent:
        _pretty_print_output_lines(
            f"actual {output_type} to match:",
            lines,
        )
        _pretty_print_output_lines(
            f"expected {output_type} as re patterns:",
            [e.as_debug_output() for e in expected],
        )

    return False


def find_modules(module: types.ModuleType) -> list[types.ModuleType]:
    modules: list[types.ModuleType] = []

    seen: set[str] = set()
    queue: deque[types.ModuleType] = deque([module])

    while queue:
        current = queue.popleft()

        if current.__name__ in seen:
            continue

        for _, potential_submodule in inspect.getmembers(current):
            if inspect.ismodule(potential_submodule):
                queue.append(potential_submodule)

        seen.add(current.__name__)
        modules.append(current)

    return modules


@cache
def find_memoised_functions_in_module(
    module: types.ModuleType,
) -> list[MemoisedFunction]:
    return [
        obj
        for _, obj in inspect.getmembers(module)
        if inspect.getmodule(obj) == module  # exclude imported functions
        and hasattr(obj, "__wrapped__")
        and hasattr(obj, "cache_clear")
    ]


def clear_memoisation_caches(root: types.ModuleType) -> None:
    modules = find_modules(root)
    functions = [fn for m in modules for fn in find_memoised_functions_in_module(m)]

    for fn in functions:
        fn.cache_clear()
