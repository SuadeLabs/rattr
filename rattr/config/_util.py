from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

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
    from rattr import error  # circular import as error.info(...) etc use config

    if arguments._follow_imports_level == 0:  # type: ignore[reportPrivateUsage]
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
