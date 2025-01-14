from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rattr import _version
from rattr.cli._util import multi_paragraph_wrap
from rattr.config import Output

if TYPE_CHECKING:
    from rattr.cli._argparse import ArgumentParser


def add_common_arguments(parser: ArgumentParser) -> ArgumentParser:
    """Apply the arguments common to the cli and toml."""
    parser = add_follow_imports_argument(parser)
    parser = add_exclude_imports_argument(parser)
    parser = add_exclude_names_argument(parser)
    parser = add_warning_level_argument(parser)
    parser = add_format_path_arguments(parser)
    parser = add_permissiveness_arguments(parser)
    parser = add_force_cache_refresh_argument(parser)
    parser = add_stdout_arguments(parser)

    return parser


def add_version_argument(parser: ArgumentParser) -> ArgumentParser:
    version_group = parser.add_argument_group()
    version_group.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {_version.version}",
    )

    return parser


def add_toml_config_override_argument(parser: ArgumentParser) -> ArgumentParser:
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        type=Path,
        required=False,
        help=multi_paragraph_wrap(
            """\
            override the default 'pyproject.toml' with another config file
            """
        ),
        metavar="TOML",
        dest="pyproject_toml_override",
    )

    return parser


def add_follow_imports_argument(parser: ArgumentParser) -> ArgumentParser:
    follow_imports_group = parser.add_argument_group()
    follow_imports_group.add_argument(
        "-f",
        "--follow-imports",
        default=1,
        type=int,
        choices=[0, 1, 2, 3],
        help=multi_paragraph_wrap(
            """\
            >follow imports level meanings:
            >    0 - do not follow imports
            >    1 - follow imports to local modules \033[1m(default)\033[0m
            >    2 - follow imports to local and pip installed modules
            >    3 - follow imports to local, pip installed, and stdlib modules

            >NB: following stdlib imports when using CPython will cause issues

            >TOML example: follow-imports=1
            """
        ),
        dest="_follow_imports_level",
    )

    return parser


def add_exclude_imports_argument(parser: ArgumentParser) -> ArgumentParser:
    exclude_imports_group = parser.add_argument_group()
    exclude_imports_group.add_argument(
        "-F",
        "--exclude-import",
        action="append",
        type=str,
        help=multi_paragraph_wrap(
            """\
            >do not follow imports to modules matching the given pattern,
            >regardless of the level of \033[1m-f\033[0m

            >TOML example: exclude-imports=['a', 'b']
            """
        ),
        metavar="PATTERN",
        dest="_excluded_imports",
    )

    return parser


def add_exclude_names_argument(parser: ArgumentParser) -> ArgumentParser:
    exclude_names_group = parser.add_argument_group()
    exclude_names_group.add_argument(
        "-x",
        "--exclude",
        action="append",
        type=str,
        help=multi_paragraph_wrap(
            """\
            >exclude functions and classes matching the
            >given regular expression from being analysed

            >TOML example: exclude=['a', 'b']
            """
        ),
        metavar="PATTERN",
        dest="_excluded_names",
    )

    return parser


def add_warning_level_argument(parser: ArgumentParser) -> ArgumentParser:
    warning_level_group = parser.add_argument_group()
    warning_level_group.add_argument(
        "-w",
        "--warning-level",
        default="default",
        type=str,
        choices=["none", "local", "default", "all"],
        help=multi_paragraph_wrap(
            """\
            >warnings level meaning:
            >    none    - do not show warnings
            >    local   - show warnings for <file>
            >    default - show warnings for all files \033[1m(default)\033[0m
            >    all     - show warnings for all files, including low-priority

            >NB: errors and fatal errors are always shown

            >TOML example: warning-level='all'
            """
        ),
        dest="_warning_level",
    )

    return parser


def add_format_path_arguments(parser: ArgumentParser) -> ArgumentParser:
    show_path_group = parser.add_argument_group()

    show_path_group.add_argument(
        "-H",
        "--collapse-home",
        action="store_true",
        help=multi_paragraph_wrap(
            """\
            >collapse the user's home directory in error messages
            >E.g.: "/home/user/path/to/file" becomes "~/path/to/file"

            >TOML example: collapse-home=true
            """
        ),
        dest="collapse_home",
    )
    show_path_group.add_argument(
        "-T",
        "--truncate-deep-paths",
        action="store_true",
        help=multi_paragraph_wrap(
            """\
            >truncate deep file paths in error messages
            >E.g.: "/home/user/very/deep/dir/to/file" becomes "/.../dir/to/file"

            >TOML example: truncate-deep-paths=true
            """
        ),
        dest="truncate_deep_paths",
    )

    return parser


def add_permissiveness_arguments(parser: ArgumentParser) -> ArgumentParser:
    strict_or_permissive_group = parser.add_argument_group()
    strict_or_permissive_mutex_group = (
        strict_or_permissive_group.add_mutually_exclusive_group()
    )

    strict_or_permissive_mutex_group.add_argument(
        "--strict",
        action="store_true",
        help=multi_paragraph_wrap(
            """\
            >select strict mode, i.e. fail on any error

            >TOML example: strict=true
            """
        ),
        dest="is_strict",
    )
    strict_or_permissive_mutex_group.add_argument(
        "--threshold",
        default=0,
        type=int,
        help=multi_paragraph_wrap(
            """\
            set the 'badness' threshold, where 0 is infinite
            \033[1m(default: --threshold 0)\033[0m

            >typical badness values:
            >    +0 - info
            >    +1 - warning
            >    +5 - error
            >    +∞ - fatal

            >NB: badness is calculated form the target file and simplification stage

            >TOML example: threshold=10
            """
        ),
        metavar="N",
        dest="threshold",
    )

    return parser


def add_force_cache_refresh_argument(parser: ArgumentParser) -> ArgumentParser:
    stdout_group = parser.add_argument_group()
    stdout_group.add_argument(
        "-r",
        "--force-refresh-cache",
        action="store_true",
        help=multi_paragraph_wrap(
            """\
            >when given delete the existing cache file, if it exists, before running

            >TOML example: force_refresh_cache=true
            """
        ),
        dest="force_refresh_cache",
    )

    return parser


def add_stdout_arguments(parser: ArgumentParser) -> ArgumentParser:
    stdout_group = parser.add_argument_group()
    stdout_group.add_argument(
        "-o",
        "--stdout",
        default=Output.results,
        type=Output,
        choices=list(Output),
        help=multi_paragraph_wrap(
            """\
            >output selection:
            >    silent  - do not print to stdout
            >    ir      - print the intermediate representation to stdout
            >    results - print the results to stdout \033[1m(default)\033[0m

            >TOML example: stdout='results'
            """
        ),
        dest="stdout",
    )

    return parser


def add_cache_file_argument(parser: ArgumentParser) -> ArgumentParser:
    target_file_group = parser.add_argument_group()
    target_file_group.add_argument(
        "-C",
        "--cache-file",
        type=Path,
        required=False,
        help=multi_paragraph_wrap(
            """\
            >the target's existing cache file
            """
        ),
        metavar="<file>",
        dest="cache_file",
    )

    return parser


def add_target_file_argument(parser: ArgumentParser) -> ArgumentParser:
    target_file_group = parser.add_argument_group()
    target_file_group.add_argument(
        "target",
        type=Path,
        help=multi_paragraph_wrap(
            """\
            >the target source file
            """
        ),
        metavar="<file>",
    )

    return parser
