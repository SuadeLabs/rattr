from __future__ import annotations

from shutil import get_terminal_size
from textwrap import dedent, fill
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

_terminal_width = get_terminal_size(fallback=(80, 32)).columns
_terminal_width_minus_argparse_indent = _terminal_width - 24


def multi_paragraph_wrap(text: str, width: int | None = None) -> str:
    """Return the given text dedented and wrapped.

    Args:
        text (str):
            The text to wrap.
        width (int | None, optional):
            The line width to wrap to. On `None` this will attempt to determine the
            current terminal width (with a fallback of 80 chars). Minimum is 16.

    Raises:
        SyntaxError: Preserved line is missing `">"`.

    Note:
        Assumes that paragraphs are separated by a double newline, with single newlines
        being removed.

        Paragraphs whose lines begin with ">" are not wrapped and have their relative
        indentation preserved. Furthermore, the string "# noqa" (and any preceding
        whitespace) is removed from the end of the lines, if present, allowing for
        linter complaints to be ignored while preserving formatting for long lines.

    Returns:
        str: The formatted text.
    """

    if width is None:
        if _terminal_width_minus_argparse_indent >= 32:
            _width = _terminal_width_minus_argparse_indent
        else:
            _width = _terminal_width
    else:
        _width = width

    _width = max(_width, 16)  # hard minimum of 16 as zero causes an error

    def _preserve(text: str) -> str:
        lines = []

        for line in text.splitlines():
            if not line.startswith(">"):
                raise SyntaxError("preserved lines must start with '>'")
            else:
                line = line[1:]

            if line.endswith("# noqa"):
                line = line[:-6].rstrip()

            lines.append(line)

        return "\n".join(fill(dedent(line), _width) for line in lines)

    def _paragraph(text: str) -> str:
        return fill(text, _width)

    paragraphs = []

    for p in dedent(text).split("\n\n"):
        if p.startswith(">"):
            paragraphs.append(_preserve(p))
        else:
            paragraphs.append(_paragraph(p))

    return "\n\n".join(p for p in paragraphs)


def get_type_name(value: Any) -> str:
    """Return a Pythonic name for the type of the given value."""
    if isinstance(value, (set, list)):
        _types: list[str] = sorted({type(v).__name__ for v in value})
        return f"{type(value).__name__}[{' | '.join(_types)}]"

    if isinstance(value, dict):
        _keys: list[str] = sorted({type(v).__name__ for v in value.keys()})
        _values: list[str] = sorted({type(v).__name__ for v in value.values()})
        return f"{type(value).__name__}[{' | '.join(_keys)}, {' | '.join(_values)}]"

    return type(value).__name__
