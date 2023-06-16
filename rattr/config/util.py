from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from rattr import error

if TYPE_CHECKING:
    from rattr.config._types import Arguments


def _is_project_root(path: Path) -> bool:
    """Return `True` if the given file is a the project root."""
    if not path.is_dir():
        return False

    is_python_project = (path / "pyproject.toml").is_file()

    is_git_repo = (path / ".git").exists()
    is_mercurial_repo = (path / ".hg").is_dir()
    is_apache_svn_repo = (path / ".svn").is_dir()

    return is_python_project or is_git_repo or is_mercurial_repo or is_apache_svn_repo


def find_project_root() -> Path:
    """Return the project root, defaults to current working directory."""
    cwd = Path.cwd().resolve()

    if _is_project_root(cwd):
        return cwd

    for dir in (dir for dir in cwd.parents if _is_project_root(dir)):
        return dir

    return cwd


def find_pyproject_toml() -> Path | None:
    """Return the project's `pyproject.toml` file."""
    pyproject_toml = find_project_root() / "pyproject.toml"

    if pyproject_toml.is_file():
        return pyproject_toml

    return None


def validate_arguments(arguments: Arguments) -> Arguments:
    """Validate and return the given arguments."""
    if arguments._follow_imports_level == 0:
        error.rattr("follow imports not set, results likely to be incomplete")

    if arguments.is_strict and arguments.threshold != 0:
        error.rattr("rattr is in --strict mode, ignoring threshold")

    if arguments.threshold < 0:
        error.fatal("threshold must be a positive integer")

    if not arguments.target.is_file():
        error.fatal(f"file {str(arguments.target)!r} does not exist")

    if arguments.target.suffix != ".py":
        error.rattr(
            f"rattr target expects '*.py', got {str(arguments.target)!r}; "
            f"did you specify the right target?"
        )

    return arguments


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
