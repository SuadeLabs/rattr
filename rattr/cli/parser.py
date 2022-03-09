import argparse
from abc import ABC, abstractstaticmethod
from argparse import ArgumentError, ArgumentParser, Namespace
from os.path import isfile, splitext

from rattr import _version, error
from rattr.cli.util import multi_paragraph_wrap


def parse_arguments() -> Namespace:
    """Return the parsed and validated CLI arguments.

    The parser is constructed and validated using the registered
    `ArgumentGroupParser`s.

    Each `ArgumentGroupParser::register` adds an
    `argparse.ArgumentParser::add_argument_group` to the parser and returns the
    parser.

    Each `ArgumentGroupParser::validate` validates the current state of the
    arguments, modifies them if need be, and returns the resulting arguments.
    If there is invalidity within the arguments, then the method should raise
    and `argparse.ArgumentError` with an appropriate message.

    On error the program usage and the error message will be shown before
    exiting.

    """
    parser: ArgumentParser = argparse.ArgumentParser(
        prog="rattr",
        description=multi_paragraph_wrap(
            """\
            Parse a given Python 3 file to find the attributes used in each
            function.

            Given the regular expression <filter-string>, the results will only
            include functions, classes, or methods whose name fully matches
            regular expression.

            Uses Python's regular expression syntax.
            """
        ),
        epilog=multi_paragraph_wrap(
            """\
            Made with ❤️ by Suade Labs.
            """
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Version
    version_group = parser.add_argument_group()
    version_group.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {_version.version}",
    )

    # TODO Allow user to add to this (will need config to respect this)
    ARGUMENT_GROUP_PARSERS = (
        FollowImports,
        ExcludeImports,
        ExcludePatterns,
        ShowWarnings,
        ShowPath,
        StrictOrPermissive,
        Output,
        FilterString,
        File,
        Cache,
    )

    for argument_group_parser in ARGUMENT_GROUP_PARSERS:
        parser = argument_group_parser.register(parser)

    # TODO
    #   One moved to Python 3.9+ add `exit_on_error=False` to the
    #   `ArgumentParser` constructor and catch the error the same as below --
    #   this will give consistent behaviour between parser and validator errors
    arguments = parser.parse_args()

    for argument_group_parser in ARGUMENT_GROUP_PARSERS:
        try:
            arguments = argument_group_parser.validate(parser, arguments)
        except ArgumentError as e:
            error.rattr(parser.format_usage())
            error.fatal(str(e))

    return arguments


class ArgumentGroupParser(ABC):
    @abstractstaticmethod
    def register(parser: ArgumentParser) -> ArgumentParser:
        return parser

    @abstractstaticmethod
    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:
        return arguments


class FollowImports(ArgumentGroupParser):
    def register(parser: ArgumentParser) -> ArgumentParser:
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
                """
            ),
        )

        return parser

    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:
        if not arguments.follow_imports:
            error.rattr("follow imports not set, results may be incomplete")

        return arguments


class ExcludeImports(ArgumentGroupParser):
    def register(parser: ArgumentParser) -> ArgumentParser:
        exclude_imports_group = parser.add_argument_group()
        exclude_imports_group.add_argument(
            "-F",
            "--exclude-import",
            action="append",
            type=str,
            help=multi_paragraph_wrap(
                """\
                do not follow imports to modules matching the given pattern,
                regardless of the level of \033[1m-f\033[0m
                """
            ),
            metavar="PATTERN",
        )

        return parser

    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:
        if arguments.exclude_import is None:
            arguments.exclude_import = list()

        return arguments


class ExcludePatterns(ArgumentGroupParser):
    def register(parser: ArgumentParser) -> ArgumentParser:
        exclude_patterns_group = parser.add_argument_group()
        exclude_patterns_group.add_argument(
            "-x",
            "--exclude",
            action="append",
            type=str,
            help=multi_paragraph_wrap(
                """\
                exclude functions and classes matching the given regular
                expression from being analysed
                """
            ),
            metavar="PATTERN",
        )

        return parser

    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:
        if arguments.exclude is None:
            arguments.exclude = list()

        return arguments


class ShowWarnings(ArgumentGroupParser):
    def register(parser: ArgumentParser) -> ArgumentParser:
        # TODO rename: all -> default, ALL -> all
        show_warnings_group = parser.add_argument_group()
        show_warnings_group.add_argument(
            "-w",
            "--show-warnings",
            default="all",
            type=str,
            choices=["none", "file", "all", "ALL"],
            help=multi_paragraph_wrap(
                """\
                >show warnings level meaning:
                >    none - do not show warnings
                >    file - show warnings for <file>
                >    all  - show warnings for all files \033[1m(default)\033[0m
                >    All  - show warnings for all files, including low-priority
                >NB: errors and fatal errors are always shown
                """
            ),
        )

        return parser

    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:
        return arguments


class ShowPath(ArgumentGroupParser):
    def register(parser: ArgumentParser) -> ArgumentParser:
        show_path_group = parser.add_argument_group()
        show_path_group.add_argument(
            "-p",
            "--show-path",
            default="short",
            type=str,
            choices=["none", "short", "full"],
            help=multi_paragraph_wrap(
                """\
                >show path level meaning:
                >    none  - do not show the file path in errors/warnings
                >    short - show an abbreviated path \033[1m(default)\033[0m
                >    full  - show the full path
                >E.g.: "/home/user/very/deep/dir/path/file" becomes "~/.../dir/path/file"  # noqa
                """
            ),
        )

        return parser

    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:
        return arguments


class StrictOrPermissive(ArgumentGroupParser):
    def register(parser: ArgumentParser) -> ArgumentParser:
        strict_or_permissive_group = parser.add_argument_group()
        strict_or_permissive_mutex_group = (
            strict_or_permissive_group.add_mutually_exclusive_group()
        )

        strict_or_permissive_mutex_group.add_argument(
            "--strict",
            action="store_true",
            help=multi_paragraph_wrap(
                """\
                run rattr in strict mode, i.e. fail on any error
                """
            ),
        )
        strict_or_permissive_mutex_group.add_argument(
            "--permissive",
            default=0,
            type=int,
            help=multi_paragraph_wrap(
                """\
                run rattr in permissive mode, with the given badness threshold
                (when threshold is zero or omitted, it is taken as infinite)
                \033[1m(default: --permissive 0 when group omitted)\033[0m

                >typical badness values:
                >    +0 - info
                >    +1 - warning
                >    +5 - error
                >    +∞ - fatal

                NB: badness is only contributed to by the target <file> and by
                the simplification stage (e.g. resolving function calls, etc).
                """
            ),
            metavar="THRESHOLD",
        )

        return parser

    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:
        if not arguments.strict:
            arguments.threshold = arguments.permissive or 0
            arguments.permissive = True
        else:
            arguments.threshold = 0
            arguments.permissive = False

        if arguments.threshold < 0:
            raise ArgumentError(None, "--permissive THRESHOLD must be positive")

        return arguments


class Output(ArgumentGroupParser):
    def register(parser: ArgumentParser) -> ArgumentParser:
        output_group = parser.add_argument_group()
        output_group.add_argument(
            "-i",
            "--show-ir",
            action="store_true",
            help=multi_paragraph_wrap(
                """\
                show the IR for the file and imports
                """
            ),
        )
        output_group.add_argument(
            "-r",
            "--show-results",
            action="store_true",
            help=multi_paragraph_wrap(
                """\
                show the results of analysis
                """
            ),
        )
        output_group.add_argument(
            "-s",
            "--show-stats",
            action="store_true",
            help=multi_paragraph_wrap(
                """\
                show stats Rattr statisitics
                """
            ),
        )
        output_group.add_argument(
            "-S",
            "--silent",
            action="store_true",
            help=multi_paragraph_wrap(
                """\
                show only errors and warnings
                """
            ),
        )

        return parser

    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:
        has_output = any(
            (arguments.show_ir, arguments.show_results, arguments.show_stats)
        )

        # Output group mutual exclusion
        # [ [-irs] | -S ]
        if has_output and arguments.silent:
            raise ArgumentError(None, "-irs and -S are mutually exclusive")

        # Output group default to -r
        if not has_output and not arguments.silent:
            arguments.show_results = True

        return arguments


class FilterString(ArgumentGroupParser):
    def register(parser: ArgumentParser) -> ArgumentParser:
        filter_string_group = parser.add_argument_group()
        filter_string_group.add_argument(
            "filter_string",
            nargs="?",
            default="",
            type=str,
            help=multi_paragraph_wrap(
                """\
                filter the output to functions matching the given regular
                expression
                """
            ),
            metavar="<filter-string>",
        )

        return parser

    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:
        if arguments.filter_string == ".*":
            arguments.filter_string = ""

        return arguments


class File(ArgumentGroupParser):
    def register(parser: ArgumentParser) -> ArgumentParser:
        file_group = parser.add_argument_group()
        file_group.add_argument(
            "file",
            nargs=1,
            type=str,
            help=multi_paragraph_wrap(
                """\
                the Python source file to analyse
                """
            ),
            metavar="<file>",
        )

        return parser

    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:
        if len(arguments.file) != 1:
            raise ArgumentError(None, "expects exactly one file")

        arguments.file = arguments.file[0]
        _, ext = splitext(arguments.file)

        if not isfile(arguments.file):
            raise ArgumentError(None, f"file '{arguments.file}' not found")

        if ext != ".py":
            error.rattr(f"expects extension '.py', got '{ext}'")

        return arguments


class Cache(ArgumentGroupParser):
    def register(parser: ArgumentParser) -> ArgumentParser:
        cache_group = parser.add_argument_group()
        cache_group.add_argument(
            "--cache",
            default="",
            type=str,
            help=multi_paragraph_wrap(
                """\
                the file to cache the results to, if successful
                """
            ),
        )

        return parser

    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:
        f = arguments.cache
        _, ext = splitext(f)

        if isfile(f):
            error.rattr(f"'{f}' already exists and will be overwritten on success")

        if f != "" and ext != ".json":
            error.rattr(f"cache expects extension '.json', got '{ext}'")

        return arguments
