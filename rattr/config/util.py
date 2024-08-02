from __future__ import annotations

import os
from pathlib import Path

from rattr import error
from rattr.config._types import Config
from rattr.config._util import (  # noqa: F401
    find_project_root,  # type: ignore[reportUnusedImport]
    find_pyproject_toml,  # type: ignore[reportUnusedImport]
    validate_arguments,  # type: ignore[reportUnusedImport]
)


def get_current_file() -> Path:
    """Return the current file or error.

    >>> # Config.state.current_file is None
    >>> get_current_file()
    ValueError("unable to get location (current file is None)")

    >>> # Config.state.current_file is Path("my_cool_file.py")
    >>> get_current_file()
    Path("my_cool_file.py")

    Raises:
        ValueError: The current file is not set.

    Returns:
        Path: The file being analysed.
    """
    config = Config()
    file = config.state.current_file

    if file is None:
        raise ValueError("unable to get location (current file is None)")

    return file


def find_xdg_cache_dir() -> Path:
    """Return the $XDG_CACHE_DIR.

    This is from the XDG Base Dir spec[1,2] which is standard on Linux.

    [1] - https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
    [2] - https://wiki.archlinux.org/title/XDG_Base_Directory
    """
    user_xdg_cache_home = os.environ.get("XDG_CACHE_HOME", None)

    default_xdg_cache_dir = Path.home() / ".cache"
    default_xdg_cache_origin = "$HOME/.cache"

    if user_xdg_cache_home is not None:
        cache_dir = Path(user_xdg_cache_home)
        origin = "$XDG_CACHE_HOME"
    else:
        cache_dir = default_xdg_cache_dir
        origin = default_xdg_cache_origin

    if not cache_dir.is_dir():
        try:
            cache_dir.mkdir(parents=True)
        except PermissionError:
            error.fatal(
                f"unable to create cache directory {origin} ({str(cache_dir)}): "
                f"permission denied"
            )

    return cache_dir
