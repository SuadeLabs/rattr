from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import Enum, IntFlag, auto
from pathlib import Path


class FollowImports(IntFlag):
    local = auto()
    pip = auto()
    stdlib = auto()


class ShowWarnings(IntFlag):
    target = auto()
    inherited_high_priority = auto()
    inherited_low_priority = auto()


class ShowPath(IntFlag):
    collapse_home = auto()
    truncate_deep_paths = auto()


class Permissiveness(Enum):
    strict = "strict"
    permissive = "permissive"


class Output(Enum):
    ir = "ir"
    results = "results"
    silent = "silent"


class CliArguments(argparse.Namespace):
    follow_imports: FollowImports

    excluded_imports: set[str]
    excluded_names: set[str]

    show_warnings: ShowWarnings

    show_path: ShowPath

    is_strict: bool
    threshold: int

    output: Output
    log_stats: bool

    filter: str | None
    """See CLI <filter-string>."""

    target: Path


@dataclass
class State:
    file_badness: int = 0
    import_badness: int = 0
    simplify_badness: int = 0

    current_file: str | None = None

    @property
    def is_in_file(self) -> bool:
        return self.current_file is not None



class ConfigMetaclass(type):
    """Metaclass allowing `Config` to act as a singleton."""
    _instance: Config | None = None

    def __call__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance: Config = super().__call__(*args, **kwargs)
        return cls._instance


@dataclass
class Config(metaclass=ConfigMetaclass):
    """The global config singleton."""
    cli: CliArguments
    state: State
