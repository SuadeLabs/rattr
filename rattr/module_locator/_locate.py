from __future__ import annotations

import os
import sys
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from rattr.module_locator.exc import RattrSysPathNotPopulated

if TYPE_CHECKING:
    from collections.abc import Iterator

    from rattr.module_locator.types import ModuleName


@cache
def locate_module_in_python_path(modulename: ModuleName) -> list[Path]:
    """Return the origins of the given module in the Python path."""
    return [
        module_location
        for search_location in iter_python_path_dirs()
        if (module_location := find_module_in_path(search_location, modulename))
    ]


def find_module_in_path(
    python_path: Path,
    modulename: ModuleName,
) -> Path | None:
    """Return the module's definition file in the given path, if extant."""
    module_parts = modulename.split(".")
    install_location = python_path.resolve()

    for part in module_parts:
        install_location /= part

    if install_location.is_dir():
        install_location /= "__init__.py"
    else:
        install_location = install_location.with_suffix(".py")

    if not install_location.exists():
        return None

    return install_location


def iter_python_path_dirs() -> Iterator[Path]:
    """Yield the extant dirs in the Python path.

    In practice this is usually the interpreter's CWD and the $PYTHONPATH, but retrieved
    from the interpreter itself not from the environment vars (which may be
    unpopulated), this is done using `sys.path` following the logic from the docs [1].

        [1] - https://docs.python.org/3/library/sys.html?highlight=sys#sys.path

    Raises:
        RattrSysPathNotPopulated: sys.paths is not populated.

    Yields:
        Iterator[Path]: The dirs in the Python path.
    """
    if not sys.path:
        raise RattrSysPathNotPopulated

    # When the sys_paths[0] is the empty string then the interpreter uses the current
    # directory (see `sys.path` docs)
    if sys.path[0] == "":
        first = os.getcwd()
    else:
        first = sys.path[0]

    yield from (
        python_path_dir
        for python_path_dirname in (first, *sys.path[1:])
        if (python_path_dir := Path(python_path_dirname))
        if python_path_dir.exists()
    )