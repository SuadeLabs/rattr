from __future__ import annotations

from functools import lru_cache
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING

from rattr.config import Config

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from importlib.machinery import ModuleSpec

    from rattr.versioning.typing import TypeAlias

    ModuleName: TypeAlias = str
    FullyQualifiedName: TypeAlias = str
    ImportLevel: TypeAlias = int


def module_exists(modulename: ModuleName) -> bool:
    return find_module_spec_fast(modulename) is not None


@lru_cache(maxsize=None)
def find_module_spec_fast(modulename: ModuleName) -> ModuleSpec | None:
    # TODO
    # In a future branch create a custom implementation which does not execute module
    # level statements in the target's parent files.
    try:
        return find_spec(modulename)
    except (AttributeError, ModuleNotFoundError, ValueError):
        return None


@lru_cache(maxsize=None)
def find_module_name_and_spec(
    target: FullyQualifiedName,
) -> tuple[ModuleName, ModuleSpec] | tuple[None, None]:
    """Return the module name and spec for the given fully qualified name.

    The fully qualified name is that of the module:
    >>> find_module_name_and_spec("math")
    ("math", ModuleSpec(name='math', loader=... origin='built-in')

    The fully qualified name is that of a module member:
    >>> find_module_name_and_spec("math.pi")
    ("math", ModuleSpec(name='math', loader=... origin='built-in')

    The fully qualified name is that of a member of a nested module:
    >>> find_module_name_and_spec("os.path.join")
    ("os.path", ModuleSpec(name='posixpath', loader=..., origin=...))

    The given name is not a fully qualified name:
    >>> find_module_name_and_spec("join")
    (None, None)
    """
    # Can't so anything with relative imports
    if target.startswith("."):
        return None, None

    for modulename in iter_module_names_right(target.split(".")):
        if (spec := find_module_spec_fast(modulename)) is not None:
            return modulename, spec

    return None, None


def iter_module_names_right(module_parts: Iterable[str]) -> Iterator[ModuleName]:
    """Return the possible module qualified names for the given parts.

    >>> list(iter_possible_modules([]))
    []

    >>> list(iter_possible_modules(["module"]))
    ["module"]

    >>> list(iter_possible_modules(["module", "sub_module"]))
    ['module.sub_module', 'module']

    >>> list(iter_possible_modules(["module", "sub_module", "file"]))
    ['module.sub_module.file', 'module.sub_module', 'module']
    """
    yield ".".join(module_parts)
    for end_offset in range(1, len(module_parts)):
        yield ".".join(module_parts[:-end_offset])


def derive_module_names_right(modulename: ModuleName) -> list[ModuleName]:
    return list(iter_module_names_right(modulename.split(".")))


def derive_module_name_from_path(filepath: Path | str | None) -> str | None:
    """Return the recognised name of the given module."""
    if filepath is None:
        raise ValueError("unable to derive the module of 'None'")

    filepath = Path(filepath)
    filepath_str = str(filepath)

    # Given a file '/path/to/repo/my_module/file/__init.py', the longest possible module
    # name would be 'path.to.repo.my_module.file' though in reality it may just be
    # 'my_module.file'
    longest_possible_modulename = (
        filepath_str.replace("/", ".")
        .replace("\\", ".")
        .removesuffix(".__init__.py")
        .removesuffix(".py")
        .strip(".")  # strip remaining "." in relative files
    )

    for module in iter_module_names_left(longest_possible_modulename.split(".")):
        if module_exists(module):
            return module

    return None


def iter_module_names_left(module_parts: Iterable[str]) -> Iterator[ModuleName]:
    """Return the possible module qualified names for the given parts.

    >>> list(iter_possible_modules([]))
    []

    >>> list(iter_possible_modules(["module"]))
    ["module"]

    >>> list(iter_possible_modules(["module", "sub_module"]))
    ['module.sub_module', 'sub_module']

    >>> list(iter_possible_modules(["module", "sub_module", "file"]))
    ['module.sub_module.file', 'sub_module.file', 'file']
    """
    for start_offset in range(len(module_parts)):
        yield ".".join(module_parts[start_offset:])


def derive_module_names_left(modulename: ModuleName) -> list[ModuleName]:
    return list(iter_module_names_left(modulename.split(".")))


def derive_absolute_module_name(
    base: ModuleName,
    target: ModuleName,
    level: ImportLevel,
) -> ModuleName:
    config = Config()

    if config.state.current_file.name == "__init__.py":
        level -= 1

    if level > 0:
        base = ".".join(base.split(".")[:-level])

    return f"{base}.{target}"
