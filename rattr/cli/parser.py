from abc import ABC, abstractstaticmethod
from argparse import ArgumentError, Namespace, RawTextHelpFormatter
from os.path import isfile, splitext
from typing import Any, Dict, List, Optional, Tuple

from tomli import TOMLDecodeError

from rattr import _version, error
from rattr.cli.argparse import _ArgumentParser as ArgumentParser
from rattr.cli.toml_parser import find_project_toml, load_cfg_from_project_toml
from rattr.cli.util import multi_paragraph_wrap


def translate_toml_cfg_to_sys_args(toml_cfg: Dict[str, Any]) -> List[str]:
    """
    Function translates pyproject.toml config dict into a sys.argv style list
    of string args (like: ['--permissive', '0', '--show-warnings', 'all', '--silent'])
    and then this is passed to the argument parses which then validates these args.
    """
    toml_sys_args = []
    for k, v in toml_cfg.items():
        arg_name = f"-{k}" if len(str(k)) == 1 else f"--{k}"
        if isinstance(v, bool):
            toml_sys_args += [arg_name] if v else []
        elif isinstance(v, str) or isinstance(v, int) or isinstance(v, float):
            toml_sys_args += [arg_name, f"{v}"]
        elif isinstance(v, list):
            for arg_value in v:
                toml_sys_args += [arg_name, f"{arg_value}"]
    return toml_sys_args


def validate_toml_cfg_arg_types(
    toml_cfg: Dict[str, Any],
    arg_group_parsers: Tuple[ABC],  # ArgumentGroupParser classes
) -> Dict[str, Any]:
    """
    Function takes the 'toml_cfg' dictionary and checks each field against
    its corresponding 'ArgumentGroupParser' class. Each ArgumentGroupParsers
    class have a 'TOML_ARG_NAME_ARG_TYPE_MAP' dict property which is a map of
    'toml_field_name' -> 'toml_field_type'.
    """
    for parser in arg_group_parsers:
        arg_name_type_map = parser.TOML_ARG_NAME_ARG_TYPE_MAP
        for arg_name, expected_arg_type in arg_name_type_map.items():
            try:
                toml_arg_val = toml_cfg[arg_name]
                if not isinstance(toml_arg_val, expected_arg_type):
                    message = (
                        f"Error parsing pyproject.toml. Arg: "
                        f"'{arg_name}' is of wrong type: "
                        f"'{type(toml_arg_val).__name__}'. "
                        f"Expected type: '{expected_arg_type.__name__}'."
                    )
                    raise ArgumentError(None, message)
            except KeyError:
                pass
    return toml_cfg


def parse_arguments(
    sys_args: Optional[List[str]] = None,
    project_toml_cfg: Optional[Dict[str, Any]] = None,
    exit_on_error: bool = True,
) -> Namespace:
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

    cli_parser: ArgumentParser = ArgumentParser(
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
        formatter_class=RawTextHelpFormatter,
        exit_on_error=exit_on_error,
    )
    # don't exit on error when .toml parser fails since we want
    # to construct our own error message saying error is from .toml file
    toml_parser: ArgumentParser = ArgumentParser(exit_on_error=False)

    # Version
    version_group = cli_parser.add_argument_group()
    version_group.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {_version.version}",
    )

    # TODO Allow user to add to this (will need config to respect this)

    # only these should be configurable in .toml file (filter and file )
    # should come from cli args
    TOML_ARG_GROUP_PARSERS = (
        FollowImports,
        ExcludeImports,
        ExcludePatterns,
        ShowWarnings,
        ShowPath,
        StrictOrPermissive,
        Output,
        Cache,
    )

    CLI_ARG_GROUP_PARSERS = TOML_ARG_GROUP_PARSERS + (FilterString, File)

    for argument_group_parser in CLI_ARG_GROUP_PARSERS:
        cli_parser = argument_group_parser.register(cli_parser)
        if argument_group_parser in TOML_ARG_GROUP_PARSERS:
            toml_parser = argument_group_parser.register(toml_parser)

    # TODO
    #   One moved to Python 3.9+ add `exit_on_error=False` to the
    #   `ArgumentParser` constructor and catch the error the same as below --
    #   this will give consistent behaviour between parser and validator errors

    # extracting .toml expected field lists from 'TOML_ARG_GROUP_PARSERS'
    toml_expected_fields: Tuple[str] = ()
    for arg_group_parser in TOML_ARG_GROUP_PARSERS:
        toml_expected_fields += tuple(
            arg_group_parser.TOML_ARG_NAME_ARG_TYPE_MAP.keys()
        )

    if not project_toml_cfg:
        try:
            toml_cfg_path = find_project_toml()
            project_toml_cfg = load_cfg_from_project_toml(toml_cfg_path=toml_cfg_path)
        except TOMLDecodeError as e:
            if exit_on_error:
                error.fatal(
                    f"Error decoding pyproject.toml file: {toml_cfg_path}. Error: {e}."
                )
            raise e

    # only keep expected fields in toml cfg dict
    project_toml_cfg = {
        k: v for k, v in project_toml_cfg.items() if k in toml_expected_fields
    }

    try:
        project_toml_cfg = validate_toml_cfg_arg_types(
            toml_cfg=project_toml_cfg,
            arg_group_parsers=TOML_ARG_GROUP_PARSERS,
        )
    except ArgumentError as e:
        if exit_on_error:
            error.fatal(e.message)
        raise e

    # construct 'sys.argv' style list of args from 'project_toml_cfg' dict
    toml_cfg_arg_list = translate_toml_cfg_to_sys_args(toml_cfg=project_toml_cfg)

    # namespace for collecting args from .toml file and sys.argv/cli args
    arguments = Namespace()

    # collect .toml args into 'Namespace' object first
    try:
        # parse args with toml_parser (which validates args at the same time),
        # this way we don't need to create a custom validation module
        # for the .toml config for cases such as mutex arg group validation etc...
        arguments = toml_parser.parse_args(args=toml_cfg_arg_list, namespace=arguments)
    except ArgumentError as e:
        if exit_on_error:
            message = (
                f"Error parsing pyproject.toml. Arg: "
                f"'{e.argument_name}', Error: {e.message}."
            )
            error.fatal(message)
        raise e

    # validate .toml args against validators
    for argument_group_parser in TOML_ARG_GROUP_PARSERS:
        try:
            if argument_group_parser is not Output:
                arguments = argument_group_parser.validate(toml_parser, arguments)
                continue
            # turn of show-results defaulting behaviour from toml file
            arguments = argument_group_parser.validate(cli_parser, arguments, toml=True)
        except ArgumentError as e:
            if exit_on_error:
                message = f"Error parsing pyproject.toml. Error: {e.message}."
                error.fatal(message)
            raise e

    # then parse cli args and overwrite overlapping toml args
    arguments = cli_parser.parse_args(
        # use empty arg Namespace (without set defaults from toml arg parsing)
        # when project_toml_cfg is empty
        namespace=arguments if project_toml_cfg else Namespace(),
        args=sys_args,
    )

    # validate args once again
    for argument_group_parser in CLI_ARG_GROUP_PARSERS:
        try:
            arguments = argument_group_parser.validate(cli_parser, arguments)
        except ArgumentError as e:
            if exit_on_error:
                error.rattr(cli_parser.format_usage())
                error.fatal(str(e))
            raise e

    return arguments


class ArgumentGroupParser(ABC):

    TOML_ARG_NAME_ARG_TYPE_MAP = {}

    @abstractstaticmethod
    def register(parser: ArgumentParser) -> ArgumentParser:
        return parser

    @abstractstaticmethod
    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:
        return arguments


class FollowImports(ArgumentGroupParser):

    ARG_LONG_NAME = "follow-imports"

    TOML_ARG_NAME_ARG_TYPE_MAP = {ARG_LONG_NAME: int}

    def register(parser: ArgumentParser) -> ArgumentParser:
        follow_imports_group = parser.add_argument_group()
        follow_imports_group.add_argument(
            "-f",
            f"--{FollowImports.ARG_LONG_NAME}",
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
        )

        return parser

    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:
        if not arguments.follow_imports:
            error.rattr("follow imports not set, results may be incomplete")

        return arguments


class ExcludeImports(ArgumentGroupParser):

    ARG_LONG_NAME = "exclude-import"

    TOML_ARG_NAME_ARG_TYPE_MAP = {ARG_LONG_NAME: list}

    def register(parser: ArgumentParser) -> ArgumentParser:
        exclude_imports_group = parser.add_argument_group()
        exclude_imports_group.add_argument(
            "-F",
            f"--{ExcludeImports.ARG_LONG_NAME}",
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
        )

        return parser

    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:
        if arguments.exclude_import is None:
            arguments.exclude_import = list()

        return arguments


class ExcludePatterns(ArgumentGroupParser):

    ARG_LONG_NAME = "exclude"

    TOML_ARG_NAME_ARG_TYPE_MAP = {ARG_LONG_NAME: list}

    def register(parser: ArgumentParser) -> ArgumentParser:
        exclude_patterns_group = parser.add_argument_group()
        exclude_patterns_group.add_argument(
            "-x",
            f"--{ExcludePatterns.ARG_LONG_NAME}",
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
        )

        return parser

    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:
        if arguments.exclude is None:
            arguments.exclude = list()

        return arguments


class ShowWarnings(ArgumentGroupParser):

    ARG_LONG_NAME = "show-warnings"

    TOML_ARG_NAME_ARG_TYPE_MAP = {ARG_LONG_NAME: str}

    def register(parser: ArgumentParser) -> ArgumentParser:
        # TODO rename: all -> default, ALL -> all
        show_warnings_group = parser.add_argument_group()
        show_warnings_group.add_argument(
            "-w",
            f"--{ShowWarnings.ARG_LONG_NAME}",
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
                >TOML example: show-warnings='all'
                """
            ),
        )

        return parser

    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:
        return arguments


class ShowPath(ArgumentGroupParser):

    ARG_LONG_NAME = "show-path"

    TOML_ARG_NAME_ARG_TYPE_MAP = {ARG_LONG_NAME: str}

    def register(parser: ArgumentParser) -> ArgumentParser:
        show_path_group = parser.add_argument_group()
        show_path_group.add_argument(
            "-p",
            f"--{ShowPath.ARG_LONG_NAME}",
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
                >TOML example: show-path='short'
                """
            ),
        )

        return parser

    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:
        return arguments


class StrictOrPermissive(ArgumentGroupParser):

    STRICT_ARG_LONG_NAME = "strict"
    PERMISSIVE_ARG_LONG_NAME = "permissive"

    TOML_ARG_NAME_ARG_TYPE_MAP = {
        STRICT_ARG_LONG_NAME: bool,
        PERMISSIVE_ARG_LONG_NAME: int,
    }

    def register(parser: ArgumentParser) -> ArgumentParser:
        strict_or_permissive_group = parser.add_argument_group()
        strict_or_permissive_mutex_group = (
            strict_or_permissive_group.add_mutually_exclusive_group()
        )

        strict_or_permissive_mutex_group.add_argument(
            f"--{StrictOrPermissive.STRICT_ARG_LONG_NAME}",
            action="store_true",
            help=multi_paragraph_wrap(
                """\
                >run rattr in strict mode, i.e. fail on any error
                >TOML example: strict=true
                """
            ),
        )
        strict_or_permissive_mutex_group.add_argument(
            f"--{StrictOrPermissive.PERMISSIVE_ARG_LONG_NAME}",
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

                >NB: badness is only contributed to by the target <file> and
                >by the simplification stage (e.g. resolving function calls, etc)
                >TOML example: permissive=10
                """
            ),
            metavar="THRESHOLD",
        )

        return parser

    def validate(parser: ArgumentParser, arguments: Namespace) -> Namespace:

        if not arguments.strict:
            # only set threshold and permissive
            # when permissive is freshly set to an int
            if isinstance(arguments.permissive, int):
                arguments.threshold = arguments.permissive or 0
                arguments.permissive = True
        else:
            arguments.threshold = 0
            arguments.permissive = False

        if arguments.threshold < 0:
            raise ArgumentError(None, "--permissive THRESHOLD must be positive")

        return arguments


class Output(ArgumentGroupParser):

    SHOW_IR_ARG_LONG_NAME = "show-ir"
    SHOW_RESULTS_ARG_LONG_NAME = "show-results"
    SHOW_STATS_ARG_LONG_NAME = "show-stats"
    SILENT_ARG_LONG_NAME = "silent"

    TOML_ARG_NAME_ARG_TYPE_MAP = {
        SHOW_IR_ARG_LONG_NAME: bool,
        SHOW_RESULTS_ARG_LONG_NAME: bool,
        SHOW_STATS_ARG_LONG_NAME: bool,
        SILENT_ARG_LONG_NAME: bool,
    }

    def register(parser: ArgumentParser) -> ArgumentParser:
        output_group = parser.add_argument_group()
        output_group.add_argument(
            "-i",
            f"--{Output.SHOW_IR_ARG_LONG_NAME}",
            action="store_true",
            help=multi_paragraph_wrap(
                """\
                >show the IR for the file and imports
                >TOML example: show-ir=true\n
                """
            ),
        )
        output_group.add_argument(
            "-r",
            f"--{Output.SHOW_RESULTS_ARG_LONG_NAME}",
            action="store_true",
            help=multi_paragraph_wrap(
                """\
                >show the results of analysis
                >TOML example: show-results=true\n
                """
            ),
        )
        output_group.add_argument(
            "-s",
            f"--{Output.SHOW_STATS_ARG_LONG_NAME}",
            action="store_true",
            help=multi_paragraph_wrap(
                """\
                >show stats Rattr statisitics
                >TOML example: show-stats=true\n
                """
            ),
        )
        output_group.add_argument(
            "-S",
            f"--{Output.SILENT_ARG_LONG_NAME}",
            action="store_true",
            help=multi_paragraph_wrap(
                """\
                >show only errors and warnings
                >TOML example: silent=true
                """
            ),
        )

        return parser

    def validate(
        parser: ArgumentParser, arguments: Namespace, toml: bool = False
    ) -> Namespace:
        has_output = any(
            (arguments.show_ir, arguments.show_results, arguments.show_stats)
        )

        # Output group mutual exclusion
        # [ [-irs] | -S ]
        if has_output and arguments.silent:
            message = (
                f"-irs ('--{Output.SHOW_IR_ARG_LONG_NAME}', "
                f"'--{Output.SHOW_RESULTS_ARG_LONG_NAME}', "
                f"'--{Output.SHOW_STATS_ARG_LONG_NAME}') "
                f"and -S ('--{Output.SILENT_ARG_LONG_NAME}') are mutually exclusive"
            )
            raise ArgumentError(None, message)

        # don't default to show-results = True when
        # output isn't configured in .toml since
        # if later cli parser brings silent mode (-S)
        # there will be a mutex validation error
        if not has_output and not arguments.silent and not toml:
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
                >filter the output to functions matching the given regular expression
                >can't be specified in .toml
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
                >the Python source file to analyse
                >can't be specified in .toml
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

    ARG_LONG_NAME = "cache"
    TOML_ARG_NAME_ARG_TYPE_MAP = {ARG_LONG_NAME: str}

    def register(parser: ArgumentParser) -> ArgumentParser:
        cache_group = parser.add_argument_group()
        cache_group.add_argument(
            f"--{Cache.ARG_LONG_NAME}",
            default="",
            type=str,
            help=multi_paragraph_wrap(
                """\
                >the file to cache the results to, if successful
                >TOML example: cache='cache.json'
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
