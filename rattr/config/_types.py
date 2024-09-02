from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from enum import Enum, IntFlag, auto
from functools import cached_property, lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from rattr.config._util import (
    find_project_root,
    find_pyproject_toml,
    validate_arguments,
)

if TYPE_CHECKING:
    from typing import Any, Final, Literal, overload


@lru_cache(maxsize=None)
def _cached_re_compile(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


class FollowImports(IntFlag):
    local = auto()
    pip = auto()
    stdlib = auto()


class ShowWarnings(IntFlag):
    target = auto()
    target_low_priority = auto()
    inherited_high_priority = auto()
    inherited_low_priority = auto()


class FormatPath(IntFlag):
    collapse_home = auto()
    truncate_deep_paths = auto()


class Output(Enum):
    stats = "stats"
    ir = "ir"
    results = "results"
    cacheable = "cacheable"
    silent = "silent"

    def __str__(self) -> str:
        return self.name


class Arguments(argparse.Namespace):
    pyproject_toml_override: Path | None
    """From `[-c PATH | --config PATH]`."""

    _follow_imports_level: Literal[0, 1, 2, 3]

    _excluded_imports: list[str] | None
    _excluded_names: list[str] | None

    _warning_level: Literal["none", "local", "default", "all"]

    collapse_home: bool
    truncate_deep_paths: bool

    is_strict: bool
    threshold: int

    stdout: Output

    force_refresh_cache: bool
    cache_file: Path | None

    target: Path

    @property
    def follow_imports(self) -> FollowImports:
        if self._follow_imports_level == 0:
            return FollowImports(0)
        if self._follow_imports_level == 1:
            return FollowImports.local
        if self._follow_imports_level == 2:
            return FollowImports.local | FollowImports.pip
        if self._follow_imports_level == 3:
            return FollowImports.local | FollowImports.pip | FollowImports.stdlib
        raise NotImplementedError

    @property
    def follow_local_imports(self) -> bool:
        return FollowImports.local in self.follow_imports

    @property
    def follow_pip_imports(self) -> bool:
        return FollowImports.pip in self.follow_imports

    @property
    def follow_stdlib_imports(self) -> bool:
        return FollowImports.stdlib in self.follow_imports

    @property
    def excluded_imports(self) -> set[str]:
        if self._excluded_imports is None:
            return set()
        return set(self._excluded_imports)

    @property
    def excluded_names(self) -> set[str]:
        if self._excluded_names is None:
            return set()
        return set(self._excluded_names)

    @property
    def re_excluded_names(self) -> tuple[re.Pattern[str], ...]:
        return tuple(_cached_re_compile(p) for p in self.excluded_names)

    @property
    def show_warnings(self) -> ShowWarnings:
        if self._warning_level == "none":
            return ShowWarnings(0)
        if self._warning_level == "local":
            return ShowWarnings.target
        if self._warning_level == "default":
            return ShowWarnings.target | ShowWarnings.inherited_high_priority
        if self._warning_level == "all":
            return (
                ShowWarnings.target
                | ShowWarnings.target_low_priority
                | ShowWarnings.inherited_high_priority
                | ShowWarnings.inherited_low_priority
            )
        raise NotImplementedError

    @property
    def format_path(self) -> FormatPath:
        flag = FormatPath(0)

        if self.collapse_home:
            flag |= FormatPath.collapse_home
        if self.truncate_deep_paths:
            flag |= FormatPath.truncate_deep_paths

        return flag


@dataclass
class State:
    badness_from_target_file: int = 0
    badness_from_imports: int = 0
    badness_from_simplification: int = 0

    current_file: "Path | None" = None

    @property
    def is_in_any_file(self) -> bool:
        return self.current_file is not None

    @property
    def badness(self) -> int:
        return self.badness_from_target_file + self.badness_from_simplification

    @property
    def full_badness(self) -> int:
        return (
            self.badness_from_target_file
            + self.badness_from_imports
            + self.badness_from_simplification
        )


class ConfigMetaclass(type):
    """Metaclass allowing `Config` to act as a singleton."""

    _instance: Config | None = None

    def __call__(cls, *args: Any, **kwargs: Any):
        if cls._instance is None:
            _instance: Config = super().__call__(*args, **kwargs)
            cls._instance = _instance
            cls._instance.arguments = validate_arguments(cls._instance.arguments)
        return cls._instance


@dataclass
class Config(metaclass=ConfigMetaclass):
    """The global config singleton."""

    arguments: Arguments
    state: State

    LITERAL_VALUE_PREFIX: Final = "@"
    """The prefix given to local constants, literals, etc to produce a name."""

    MODULE_BLACKLIST_PATTERNS: Final = frozenset(
        (
            r"rattr",
            r"rattr\..*",
            r"packages?\.rattr",
            r"packages?\.rattr\..*",
        )
    )
    """The set of perennial module blacklist patterns, i.e. rattr itself."""

    PLUGINS_BLACKLIST_PATTERNS: set[str] = field(default_factory=set)
    """The set of blacklist patterns set by custom plugins."""

    if TYPE_CHECKING:

        @overload
        def __init__(self) -> None:  # type: ignore[reportNoOverloadImplementation]
            ...

        @overload
        def __init__(  # type: ignore[reportNoOverloadImplementation]
            self,
            arguments: Arguments,
            state: State,
        ) -> None:
            ...

        @overload
        def __init__(  # type: ignore[reportNoOverloadImplementation]
            self,
            arguments: Arguments,
            state: State,
            PLUGINS_BLACKLIST_PATTERNS: set[str],
        ) -> None:
            ...

    @cached_property
    def project_root(self) -> Path:
        return find_project_root()

    @cached_property
    def pyproject_toml(self) -> Path | None:
        return find_pyproject_toml()

    @cached_property
    def root_cache_dir(self) -> Path:
        return self.project_root / ".rattr" / "cache"

    @property
    def is_in_target_file(self) -> bool:
        return self.arguments.target == self.state.current_file

    @property
    def do_not_follow_imports(self) -> bool:
        return self.arguments.follow_imports == FollowImports(0)

    @property
    def do_not_show_warnings(self) -> bool:
        return self.arguments.show_warnings == ShowWarnings(0)

    @property
    def use_full_path(self) -> bool:
        return self.arguments.format_path == FormatPath(0)

    def increment_badness(self, badness: int) -> None:
        """Increment the appropriate badness level based on state."""
        if badness < 0:
            raise ValueError("'badness' must be positive integer")

        if not self.state.is_in_any_file:
            self.state.badness_from_simplification += badness
        elif self.is_in_target_file:
            self.state.badness_from_target_file += badness
        else:
            self.state.badness_from_imports += badness

    @property
    def is_within_badness_threshold(self) -> int:
        if self.arguments.is_strict:
            return self.state.badness <= 0

        # A threshold of zero is equivalent to infinite
        if self.arguments.threshold == 0:
            return True

        return self.state.badness <= self.arguments.threshold

    def get_formatted_path(self, path: Path | str | None) -> str | None:
        if path is None:
            return None

        if isinstance(path, str):
            path = Path(path)

        home = str(Path.home().resolve())

        if path.is_relative_to(self.project_root):
            path = path.relative_to(self.project_root)

        if self.arguments.collapse_home and path.is_relative_to(home):
            relative_path = str(path).replace(home, "")

            if relative_path.startswith(("/", "\\")):
                relative_path = relative_path[1:]

            path = Path("~") / relative_path

        if self.arguments.truncate_deep_paths and len(path.parts) > 5:
            base = Path(path.parts[0]) / "..."

            for part in path.parts[-3:]:
                base /= part

            path = base

        return path.as_posix()

    @property
    def formatted_current_file_path(self) -> str | None:
        return self.get_formatted_path(self.state.current_file)

    @property
    def formatted_target_path(self) -> str | None:
        return self.get_formatted_path(self.arguments.target)

    @property
    def blacklist_patterns(self) -> set[str]:
        return (
            self.arguments.excluded_imports
            | self.MODULE_BLACKLIST_PATTERNS
            | self.PLUGINS_BLACKLIST_PATTERNS
        )

    @property
    def re_blacklist_patterns(self) -> tuple[re.Pattern[str], ...]:
        return tuple(_cached_re_compile(p) for p in self.blacklist_patterns)
