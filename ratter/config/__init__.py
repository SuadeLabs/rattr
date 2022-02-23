from dataclasses import dataclass, field
from typing import Optional, Set

from ratter.cache import RatterCache


@dataclass
class Config:
    """Hold Ratter run-time configuration.

    NOTE
        Defaults only used in tests, `__main__.py` will always override

    """

    dry_run: bool = False

    # Import following
    follow_imports: int = 1
    follow_pip_imports: bool = False
    follow_stdlib_imports: bool = False

    # Exclusions
    excluded_imports: Set[str] = field(default_factory=set)
    excluded_names: Set[str] = field(default_factory=set)

    # Warnings
    show_warnings: bool = True
    show_imports_warnings: bool = True
    show_low_priority_warnings: bool = False

    # File name in error messages
    show_path: bool = True
    use_short_path: bool = True

    # Results and output
    show_ir: bool = False
    show_results: bool = True
    show_stats: bool = False
    silent: bool = False

    # Error threshold
    strict: bool = False
    permissive: bool = True
    threshold: int = 0
    file_badness: int = 0
    import_badness: int = 0
    simplify_badness: int = 0

    # Results filtering
    filter_string: str = ""

    # File info
    file: str = "<no_file>"

    # File to save cache results to
    save_results: str = ""

    # Cache settings
    use_cache: bool = False
    save_cache: bool = False

    # HACK Below items constitute run-time state and are not strictly config
    # TODO
    #   Move state somewhere intelligent, without having to pass state
    #   to/through dozens of functions making the function signatures messier
    #   than needed

    # See `util.py::enter_file`
    current_file: Optional[str] = None

    # See `RatterCache`
    cache: RatterCache = field(default_factory=RatterCache)


config = Config()
