from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from rattr.config._types import Config

if TYPE_CHECKING:
    from collections.abc import Generator


@contextmanager
def enter_file(new_file: Path | str | None) -> Generator[None, None, None]:
    """Set the config state's current file to the given file while in scope.

    >>> config = Config()
    >>> visited: list[Path] = []
    >>> with enter_file(Path("target_file.py")):
    ...     visited.append(config.state.current_file)
    ...     with enter_file(Path("an_imported_file.py")):
    ...         visited.append(config.state.current_file)
    ...     visited.append(config.state.current_file)
    >>> print(visited)
    [Path("target_file.py"), Path("an_imported_file.py"), Path("target_file.py")]
    """
    config = Config()

    if isinstance(new_file, str):
        new_file = Path(new_file)

    old_file = config.state.current_file
    config.state.current_file = new_file

    yield

    config.state.current_file = old_file
