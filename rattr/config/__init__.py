from dataclasses import dataclass, field
from typing import Optional, Set


@dataclass
class Config:
    """Hold Rattr run-time configuration.

    NOTE
        Defaults only used in tests, `__main__.py` will always override

    """

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

    # HACK State, cleaner than passing [str | None] to dozens of functions
    # NOTE See `util.py::enter_file`
    current_file: Optional[str] = None

    # Cache file
    cache: str = ""


config = Config()
