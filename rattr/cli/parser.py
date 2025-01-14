from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from rattr import error
from rattr.cli import _arguments
from rattr.cli._argparse import ArgumentParser
from rattr.cli._types import TomlArgumentType
from rattr.cli._util import get_type_name, multi_paragraph_wrap
from rattr.cli.toml import TOMLDecodeError, parse_project_toml
from rattr.config import Arguments
from rattr.config.util import find_pyproject_toml

if TYPE_CHECKING:
    from typing import Any, NoReturn


TOML_ARGUMENT_NAME_TO_SYS_ARGUMENT_NAME_MAP: dict[str, str] = {
    "exclude-imports": "exclude-import",
}
"""Map from toml argument name to sys argument name.

If absent the name is the same for both the toml arguments and the sys arguments, thus
the expected usage is as such:

>>> # TOML_ARGUMENT_NAME_TO_SYS_ARGUMENT_NAME_MAP = {"saul-of-tarsus": "paul"}
>>> toml_name = "peter"
>>> TOML_ARGUMENT_NAME_TO_SYS_ARGUMENT_NAME_MAP.get(toml_name, toml_name)
"peter"
>>> toml_name = "saul-of-tarsus"
>>> TOML_ARGUMENT_NAME_TO_SYS_ARGUMENT_NAME_MAP.get(toml_name, toml_name)
"paul"
"""

TOML_ARGUMENT_TYPE_MAP: dict[str, TomlArgumentType] = {
    "follow-imports": TomlArgumentType.int,
    "exclude-imports": TomlArgumentType.list_of_strings,
    "exclude": TomlArgumentType.list_of_strings,
    "warning-level": TomlArgumentType.string,
    "collapse-home": TomlArgumentType.flag,
    "truncate-deep-paths": TomlArgumentType.flag,
    "strict": TomlArgumentType.flag,
    "threshold": TomlArgumentType.int,
    "stdout": TomlArgumentType.string,
}
"""The expected type of the arguments in the toml config file.

This is used for:
1. Type checking the provided toml arguments;
2. Correctly converting toml arguments to sys arguments (see TomlArgumentType docs).
"""


def parse_arguments(
    *,
    sys_args: list[str] | None = None,
    project_toml_conf: dict[str, Any] | None = None,
    exit_on_error: bool = True,
) -> Arguments:
    cli_parser = make_cli_parser(exit_on_error=exit_on_error)
    toml_parser = make_toml_parser()

    project_toml_conf = _parse_project_config(
        project_toml_conf,
        _get_toml_override(cli_parser, sys_args=sys_args),
        exit_on_error=exit_on_error,
    )
    toml_arguments = _translate_toml_conf_to_sys_args(project_toml_conf)

    # Parse the arguments from the project toml
    # Then add/override with the arguments from the cli
    arguments = Arguments()
    try:
        toml_parser.parse_args(args=toml_arguments, namespace=arguments)
    except argparse.ArgumentError as argument_error:
        _toml_error(argument_error, exit_on_error=exit_on_error)
    cli_parser.parse_args(args=sys_args, namespace=arguments)

    return arguments


def make_cli_parser(exit_on_error: bool = True) -> ArgumentParser:
    parser = ArgumentParser(
        prog="rattr",
        description=multi_paragraph_wrap(
            """\
            Parse a given Python 3 file to find the attributes used in each function.

            Arguments of type "PATTERN" use Python's regular expression syntax.
            """
        ),
        epilog=multi_paragraph_wrap(
            """\
            Made with ❤️ by Suade Labs.
            """
        ),
        formatter_class=argparse.RawTextHelpFormatter,
        exit_on_error=exit_on_error,
    )

    parser = _arguments.add_version_argument(parser)
    parser = _arguments.add_toml_config_override_argument(parser)
    parser = _arguments.add_common_arguments(parser)
    parser = _arguments.add_cache_file_argument(parser)
    parser = _arguments.add_target_file_argument(parser)

    return parser


def make_toml_parser() -> ArgumentParser:
    parser = ArgumentParser(exit_on_error=False)
    parser = _arguments.add_common_arguments(parser)

    return parser


def _get_toml_override(
    cli_parser: ArgumentParser,
    *,
    sys_args: list[str] | None = None,
) -> Path | None:
    """Return the toml config override from the CLI if given, otherwise `None`."""
    cli_arguments = cli_parser.parse_args(args=sys_args, namespace=Arguments())
    pyproject_toml_override = cli_arguments.pyproject_toml_override

    if pyproject_toml_override and pyproject_toml_override.is_file():
        return pyproject_toml_override

    return None


def _toml_error(exc: Exception, *, exit_on_error: bool) -> NoReturn:
    if exit_on_error:
        error.fatal(f"error parsing project toml: {error}")
    raise exc


def _parse_project_config(
    input_config: dict[str, Any] | None,
    project_toml_override: Path | None,
    *,
    exit_on_error: bool = True,
) -> dict[str, Any]:
    pyproject_toml = find_pyproject_toml()

    # Allow the use of an explicit config
    # This is helpful for testing and for making rattr derived projects
    if not input_config:
        try:
            conf = parse_project_toml(pyproject_toml, project_toml_override)
        except TOMLDecodeError as toml_decode_error:
            _toml_error(toml_decode_error, exit_on_error=exit_on_error)
    else:
        conf = input_config

    try:
        conf = _validate_toml_config(conf)
    except argparse.ArgumentError as argument_error:
        _toml_error(argument_error, exit_on_error=exit_on_error)

    return conf


def _validate_toml_config(conf: dict[str, Any]) -> dict[str, Any]:
    _type_error: str = (
        "{arg!r} expects type {expected_type}, got {value!r} of type {actual_type}"
    )

    # Prune unrecognised arguments
    toml_supported_arguments = TOML_ARGUMENT_TYPE_MAP.keys()
    conf = {k: v for k, v in conf.items() if k in toml_supported_arguments}

    # Validate types
    for arg, value in conf.items():
        expected_type = TOML_ARGUMENT_TYPE_MAP[arg]

        if not expected_type.is_valid(value):
            _error = _type_error.format(
                arg=arg,
                value=value,
                expected_type=str(expected_type),
                actual_type=get_type_name(value),
            )
            raise argparse.ArgumentError(None, _error)

    return conf


def _translate_toml_conf_to_sys_args(toml_conf: dict[str, Any]) -> list[str]:
    """Return the toml conf translated to `sys.argv` style list.

    >>> _translate_toml_conf_to_sys_args(
    ...     {"threshold": 10, "warning-level": "all", "exclude": ["a", "b"]}
    ... )
    ["--threshold", "0", "--warning-level", "all", "--exclude", "a", "--exclude", "b"]
    """
    toml_sys_args: list[str] = []

    for k, v in toml_conf.items():
        if len(k) > 1:
            arg_name = f"--{TOML_ARGUMENT_NAME_TO_SYS_ARGUMENT_NAME_MAP.get(k, k)}"
        else:
            arg_name = f"-{k}"

        if isinstance(v, bool):
            toml_sys_args += [arg_name] if v else []
        elif isinstance(v, str) or isinstance(v, int) or isinstance(v, float):
            toml_sys_args += [arg_name, f"{v}"]
        elif isinstance(v, list):
            for arg_value in v:
                toml_sys_args += [arg_name, f"{arg_value}"]

    return toml_sys_args
