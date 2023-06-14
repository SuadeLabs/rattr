from __future__ import annotations

from shutil import get_terminal_size
from textwrap import dedent, fill

_terminal_width = get_terminal_size(fallback=(80, 32)).columns


def multi_paragraph_wrap(text: str, width: int | None = None) -> str:
    """Return the given text dedented and wrapped.

    Args:
        text (str):
            The text to wrap.
        width (int | None, optional):
            The line width to wrap to. On `None` this will attempt to determine the
            current terminal width (with a fallback of 80 chars).

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
        width = _terminal_width

    def _preserve(text: str) -> str:
        lines = list()

        for line in text.splitlines():
            if not line.startswith(">"):
                raise SyntaxError("preserved lines must start with '>'")
            else:
                line = line[1:]

            if line.endswith("# noqa"):
                line = line[:-6].rstrip()

            lines.append(line)

        return "\n".join(fill(dedent(line), width) for line in lines)

    def _paragraph(text: str) -> str:
        return fill(text, width)

    paragraphs = list()

    for p in dedent(text).split("\n\n"):
        if p.startswith(">"):
            paragraphs.append(_preserve(p))
        else:
            paragraphs.append(_paragraph(p))

    return "\n\n".join(p for p in paragraphs)
