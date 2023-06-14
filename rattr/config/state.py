from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from config._types import Config

if TYPE_CHECKING:
    from collections.abc import Generator


@contextmanager
def enter_file(new_file: str) -> Generator[None, None, None]:
    """Set the config state's current file to the given file while in scope.

    >>> config = Config()
    >>> visited: list[str] = []
    >>> with enter_file("target_file.py"):
    ...     visited.append(config.state.current_file)
    ...     with enter_file("an_imported_file.py"):
    ...         visited.append(config.state.current_file)
    ...     visited.append(config.state.current_file)
    >>> print(visited)
    ["target_file.py", "an_imported_file.py", "target_file.py"]
    """
    config = Config()

    old_file = config.state.current_file
    config.state.current_file = new_file

    yield

    config.state.current_file = old_file
