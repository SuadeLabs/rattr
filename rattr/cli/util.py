"""Rattr CLI parser util functions."""

from argparse import Namespace
from textwrap import dedent, fill
from typing import Any, Dict


def multi_paragraph_wrap(text: str, width: int = 80) -> str:
    """Return the text dedented and wrapped at 70 characters.

    Assumes that paragraphs are separated by a double newline, with single
    newlines being removed.

    Paragraphs whose lines begin with ">" have their singlelines and relative
    indentation preserved. Furthermore, the string "# noqa" (and any preceding
    whitespace) is removed from the end of the lines, if present, allowing for
    linter complaints to be ignored while preserving formatting for long lines.

    """

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


def namespace_to_dict(arguments: Namespace) -> Dict[str, Any]:
    """Return the given arguments as a dictionary."""
    return {k: v for k, v in arguments._get_kwargs()}
