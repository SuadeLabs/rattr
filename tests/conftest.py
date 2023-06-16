from __future__ import annotations

import ast
import sys
from contextlib import contextmanager
from importlib.util import find_spec
from os.path import dirname, join
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from rattr.analyser.base import CustomFunctionAnalyser, CustomFunctionHandler
from rattr.analyser.context import Context, RootContext
from rattr.analyser.context.symbol import Builtin, Call, Name, Symbol
from rattr.analyser.file import FileAnalyser
from rattr.analyser.results import generate_results_from_ir
from rattr.analyser.types import FileIR, FuncOrAsyncFunc, FunctionIR
from rattr.analyser.util import LOCAL_VALUE_PREFIX, has_affect
from rattr.cli.parser import (
    ExcludeImports,
    ExcludePatterns,
    FollowImports,
    Output,
    SaveResults,
    ShowPath,
    ShowWarnings,
    StrictOrPermissive,
)
from rattr.config import Arguments, Config, Output, State

if TYPE_CHECKING:
    from typing import Callable

    from rattr.analyser.types import FileResults


def pytest_configure(config):
    config.addinivalue_line("addopts", "--strict-markers")

    config.addinivalue_line("markers", "pypy: mark test to run only under pypy")
    config.addinivalue_line(
        "markers", "py_3_8_plus: mark test to run only under Python 3.8+"
    )
    config.addinivalue_line(
        "markers",
        "update_expected_results: mark test that updates the expected test results for "
        "a benchmarking test, only run if the mark is explicitly given",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]):
    """Alter the collected tests."""
    if not is_pypy():
        skip_test_items_with_mark(items, "pypy")

    if not is_python_3_8_plus():
        skip_test_items_with_mark(items, "py_3_8_plus")

    skip_test_items_with_mark_if_not_explicitly_given(
        items,
        "update_expected_results",
        config=config,
    )


def skip_test_items_with_mark(items: list[pytest.Item], mark: str):
    """Remove the marked items if the condition is `False`."""
    _reason = "{mark} is not satisfied"

    for item in (i for i in items if i.get_closest_marker(mark)):
        item.add_marker(pytest.mark.skip(reason=_reason.format(mark=mark)))


def skip_test_items_with_mark_if_not_explicitly_given(
    items: list[pytest.Item],
    mark: str,
    *,
    config: pytest.Config,
):
    """Skip tests with the given mark unless the mark was given via `-m mark` etc."""
    dash_m_is_in_cli_arguments = bool(config.option.markexpr)
    dash_k_is_in_cli_arguments = bool(config.option.keyword)

    if dash_m_is_in_cli_arguments or dash_k_is_in_cli_arguments:
        # If `-m ...` or `-k ...` is given, let pytest handle the skipping/running
        # i.e. the test will only run if it is in the `-m` or the `-k`
        return

    skip_test_items_with_mark(items, mark)


def is_pypy():
    """Return `True` if running under pypy."""
    return find_spec("__pypy__") is not None


def is_python_3_8_plus():
    """Return `True` if running under Python 3.8 plus."""
    if sys.version_info.major != 3:
        raise NotImplementedError

    if sys.version_info.minor >= 8:
        return True
    else:
        return False


@pytest.fixture(scope="session", autouse=True)
@mock.patch("rattr.config._types.validate_arguments", lambda args: args)
def setup_config():
    Config(
        arguments=Arguments(
            pyproject_toml_override=None,
            _follow_imports_level=1,
            _excluded_imports=set(),
            _excluded_names=set(),
            _warning_level="default",
            _collapse_home=True,
            _truncate_deep_paths=True,
            is_strict=False,
            threshold=0,
            stdout=Output.results,
            target=Path(),
        ),
        state=State(),
    )


@pytest.fixture
def parse():
    def _inner(source: str) -> ast.AST:
        """Return the parsed AST for the given code, use relative indentation.

        Assume usage is:
            parse('''
                <source code>       # first line sets the base indent
                <source code>
                    <source code>   # this is indented once (relative)
                <source code>
            ''')

        Require the opening and closing blank lines.
        """
        lines = list()
        source_lines = source.splitlines()[1:-1]

        if not len(source_lines):
            raise ValueError("Incorrect source code formatting")

        # Determine whitespace from first line
        indent = str()
        for c in source_lines[0]:
            if not c.isspace():
                break
            indent += c

        # Strip whitespace from all lines
        for line in source_lines:
            if line.startswith(indent):
                lines.append(line[len(indent) :])
            elif line == "":
                lines.append(line)
            else:
                raise SyntaxError("Incorrect indentation in test code")

        return ast.parse("\n".join(lines))

    return _inner


@pytest.fixture
def parse_with_context(parse: Callable[[str], ast.AST]):
    def _inner(source: str) -> tuple[ast.AST, Context]:
        _ast = parse(source)
        _ctx = RootContext(_ast)
        return _ast, _ctx

    return _inner


@pytest.fixture
def analyse_single_file(parse_with_context: Callable[[str], tuple[ast.AST, Context]]) -> Callable[[str], tuple[FileIR, FileResults]]:
    """Parse and analyse the source as though it were a single file.

    NOTE
        This does not follow imports, for that we will need a more complex fixture or to
        wait for the new config code to be merged s.t. we can mock the config easier and
        call the functions used in __main__.py more directly.
    """
    def _inner(source: str) -> tuple[ast.AST, Context]:
        _ast, _ctx = parse_with_context(source)
        file_ir = FileAnalyser(_ast, _ctx).analyse()
        file_results = generate_results_from_ir(file_ir, {})

        return file_ir, file_results

    return _inner


@pytest.fixture
def root_context_with() -> Callable[[list[Symbol]], Context]:
    def _inner(extra: list[Symbol]) -> Context:
        context = RootContext(ast.Module(body=[]))
        context.add_all(extra)
        return context

    return _inner


@pytest.fixture
def builtin() -> Callable[[str], Builtin]:
    def _inner(name: str) -> Builtin:
        return Builtin(name, has_affect=has_affect(name))

    return _inner


@pytest.fixture
def RootSymbolTable():
    def _inner(*args):
        """Create a root context with the addition of the **kwargs."""
        symtab = RootContext(ast.Module(body=[])).symbol_table

        for s in args:
            symtab.add(s)

        return symtab

    return _inner


@pytest.fixture(scope="function", autouse=True)
def _set_current_file(config) -> None:
    with config("current_file", "_in_test.py"):
        yield


@pytest.fixture()
def run_in_strict_mode(config) -> None:
    with config("strict", True):
        yield


@pytest.fixture()
def run_in_permissive_mode(config) -> None:
    with config("strict", False):
        yield


@pytest.fixture
def argument():
    @contextmanager
    def _inner(attr, value):
        arguments = Config().arguments

        if not hasattr(arguments, attr):
            raise AttributeError

        _previous = getattr(arguments, attr)
        setattr(arguments, attr, value)
        yield
        setattr(arguments, attr, _previous)

    return _inner


@pytest.fixture
def state():
    @contextmanager
    def _inner(attr, value):
        state = Config().state

        if not hasattr(state, attr):
            raise AttributeError

        _previous = getattr(state, attr)
        setattr(state, attr, value)
        yield
        setattr(state, attr, _previous)

    return _inner


@pytest.fixture
def stdlib_modules():
    # Scraped from python.org
    scraped = {
        "string",
        "re",
        "difflib",
        "textwrap",
        "unicodedata",
        "stringprep",
        "rlcompleter",
        "struct",
        "codecs",
        "datetime",
        "calendar",
        "collections",
        "abc",
        "heapq",
        "bisect",
        "array",
        "weakref",
        "types",
        "copy",
        "pprint",
        "reprlib",
        "enum",
        "numbers",
        "math",
        "cmath",
        "decimal",
        "fractions",
        "random",
        "statistics",
        "itertools",
        "functools",
        "operator",
        "pathlib",
        "fileinput",
        "stat",
        "filecmp",
        "tempfile",
        "glob",
        "fnmatch",
        "linecache",
        "shutil",
        "pickle",
        "copyreg",
        "shelve",
        "dbm",
        "sqlite3",
        "zlib",
        "gzip",
        "bz2",
        "lzma",
        "zipfile",
        "tarfile",
        "csv",
        "configparser",
        "netrc",
        "xdrlib",
        "plistlib",
        "hashlib",
        "hmac",
        "secrets",
        "os",
        "io",
        "time",
        "argparse",
        "getopt",
        "logging",
        "getpass",
        "curses",
        "platform",
        "errno",
        "ctypes",
        "threading",
        "multiprocessing",
        "concurrent",
        "subprocess",
        "sched",
        "queue",
        "_thread",
        "asyncio",
        "asyncio",
        "socket",
        "ssl",
        "select",
        "selectors",
        "asyncore",
        "asynchat",
        "signal",
        "mmap",
        "email",
        "json",
        "mailcap",
        "mailbox",
        "mimetypes",
        "base64",
        "binhex",
        "binascii",
        "quopri",
        "uu",
        "html",
        "webbrowser",
        "cgi",
        "cgitb",
        "wsgiref",
        "urllib",
        "http",
        "ftplib",
        "poplib",
        "imaplib",
        "nntplib",
        "smtplib",
        "smtpd",
        "telnetlib",
        "uuid",
        "socketserver",
        "xmlrpc",
        "ipaddress",
        "audioop",
        "aifc",
        "sunau",
        "wave",
        "chunk",
        "colorsys",
        "imghdr",
        "sndhdr",
        "ossaudiodev",
        "gettext",
        "locale",
        "turtle",
        "cmd",
        "shlex",
        "typing",
        "pydoc",
        "doctest",
        "unittest",
        "test",
        "bdb",
        "faulthandler",
        "pdb",
        "timeit",
        "trace",
        "tracemalloc",
        "distutils",
        "venv",
        "zipapp",
        "sys",
        "sysconfig",
        "builtins",
        "warnings",
        "dataclasses",
        "contextlib",
        "abc",
        "atexit",
        "traceback",
        "gc",
        "inspect",
        "site",
        "code",
        "codeop",
        "pkgutil",
        "modulefinder",
        "runpy",
        "importlib",
        "ast",
        "symtable",
        "token",
        "keyword",
        "tokenize",
        "tabnanny",
        "pyclbr",
        "py_compile",
        "compileall",
        "dis",
        "pickletools",
        "spwd",
        "crypt",
        "tty",
        "pty",
        "pipes",
        "nis",
        "optparse",
        "imp",
    }

    return scraped


@pytest.fixture
def builtins():
    generated = {
        "abs",
        "all",
        "any",
        "ascii",
        "bin",
        "bool",
        "breakpoint",
        "bytearray",
        "bytes",
        "callable",
        "chr",
        "classmethod",
        "compile",
        "complex",
        "copyright",
        "credits",
        "delattr",
        "dict",
        "dir",
        "divmod",
        "enumerate",
        "eval",
        "exec",
        "filter",
        "float",
        "format",
        "frozenset",
        "getattr",
        "globals",
        "hasattr",
        "hash",
        "help",
        "hex",
        "id",
        "input",
        "int",
        "isinstance",
        "issubclass",
        "iter",
        "len",
        "license",
        "list",
        "locals",
        "map",
        "max",
        "memoryview",
        "min",
        "next",
        "object",
        "oct",
        "open",
        "ord",
        "pow",
        "print",
        "property",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "setattr",
        "slice",
        "sorted",
        "staticmethod",
        "str",
        "sum",
        "super",
        "tuple",
        "type",
        "vars",
        "zip",
    }

    return generated


@pytest.fixture
def snippet():
    def _inner(relative_path: str):
        return join(dirname(__file__), "snippets", relative_path)

    return _inner


@pytest.fixture
def file_ir_from_dict():
    def _inner(ir):
        # Make quasi-context
        ctx = Context(None)
        ctx.add_all(ir.keys())

        # Create FileIR
        file_ir = FileIR(ctx)
        file_ir._file_ir = ir

        return file_ir

    return _inner


class _PrintBuiltinAnalyser(CustomFunctionAnalyser):
    @property
    def name(self) -> str:
        return "print"

    @property
    def qualified_name(self) -> str:
        return "print"

    def on_def(self, name: str, node: FuncOrAsyncFunc, ctx: Context) -> FunctionIR:
        return {
            "sets": {
                Name("set_in_print_def"),
            },
            "gets": {
                Name("get_in_print_def"),
            },
            "dels": {
                Name("del_in_print_def"),
            },
            "calls": {
                Call("call_in_print_def", [], {}, None),
            },
        }

    def on_call(self, name: str, node: ast.Call, ctx: Context) -> FunctionIR:
        return {
            "sets": {
                Name("set_in_print"),
            },
            "gets": {
                Name("get_in_print"),
            },
            "dels": {
                Name("del_in_print"),
            },
            "calls": {
                Call("call_in_print", [], {}, None),
            },
        }


@pytest.fixture
def PrintBuiltinAnalyser():
    return _PrintBuiltinAnalyser


class _ExampleFuncAnalyser(CustomFunctionAnalyser):
    @property
    def name(self) -> str:
        return "example"

    @property
    def qualified_name(self) -> str:
        return "module.example"

    def on_def(self, name: str, node: FuncOrAsyncFunc, ctx: Context) -> FunctionIR:
        return {
            "sets": {
                Name("set_in_example_def"),
            },
            "gets": {
                Name("get_in_example_def"),
            },
            "dels": {
                Name("del_in_example_def"),
            },
            "calls": {
                Call("call_in_example_def", [], {}, None),
            },
        }

    def on_call(self, name: str, node: ast.Call, ctx: Context) -> FunctionIR:
        return {
            "sets": {
                Name("set_in_example"),
            },
            "gets": {
                Name("get_in_example"),
            },
            "dels": {
                Name("del_in_example"),
            },
            "calls": {
                Call("call_in_example", [], {}, None),
            },
        }


@pytest.fixture
def ExampleFuncAnalyser():
    return _ExampleFuncAnalyser


@pytest.fixture
def handler():
    handler = CustomFunctionHandler([_PrintBuiltinAnalyser()], [_ExampleFuncAnalyser()])

    return handler


@pytest.fixture
def constant():
    """Return the version specific name for a constant of the given type.

    In Python <= 3.7, constants are named as such "@Str", "@Num", etc.

    In Python >= 3.8, constants are all named "@Constant".

    """

    def _inner(node_type: str):
        if sys.version_info.major != 3:
            raise AssertionError

        if sys.version_info.minor <= 7:
            return f"{LOCAL_VALUE_PREFIX}{node_type}"
        else:
            return f"{LOCAL_VALUE_PREFIX}Constant"

    return _inner


@pytest.fixture
def illegal_field_name():
    return "illegal-field"


@pytest.fixture
def toml_dict_with_illegal_fields():
    return {
        FollowImports.ARG_LONG_NAME: 3,
        ExcludeImports.ARG_LONG_NAME: [
            "a\\.b\\.c",
            "a\\.b.*",
            "a\\.b\\.c\\.e",
            "a\\.b\\.c.*",
        ],
        ExcludePatterns.ARG_LONG_NAME: ["a_.*", "b_.*", "_.*"],
        ShowWarnings.ARG_LONG_NAME: "all",
        illegal_field_name: "full",  # bad field name
        StrictOrPermissive.PERMISSIVE_ARG_LONG_NAME: 1,
        Output.SHOW_IR_ARG_LONG_NAME: True,
        Output.SHOW_RESULTS_ARG_LONG_NAME: True,
        Output.SHOW_STATS_ARG_LONG_NAME: True,
        SaveResults.ARG_LONG_NAME: "results.json",
    }


@pytest.fixture
def toml_dict_with_bad_field_types_and_error1():
    return {
        FollowImports.ARG_LONG_NAME: "abcd",  # bad field type
        ExcludeImports.ARG_LONG_NAME: [
            "a\\.b\\.c",
            "a\\.b.*",
            "a\\.b\\.c\\.e",
            "a\\.b\\.c.*",
        ],
        ExcludePatterns.ARG_LONG_NAME: ["a_.*", "b_.*", "_.*"],
        ShowWarnings.ARG_LONG_NAME: "all",
        ShowPath.ARG_LONG_NAME: "full",
        StrictOrPermissive.PERMISSIVE_ARG_LONG_NAME: 1,
        Output.SHOW_IR_ARG_LONG_NAME: True,
        Output.SHOW_RESULTS_ARG_LONG_NAME: True,
        Output.SHOW_STATS_ARG_LONG_NAME: True,
        SaveResults.ARG_LONG_NAME: "rattr/cli/parser.py",
    }, (
        f"Error parsing pyproject.toml. Arg: '{FollowImports.ARG_LONG_NAME}' "
        f"is of wrong type: 'str'. Expected type: "
        f"'{FollowImports.TOML_ARG_NAME_ARG_TYPE_MAP[FollowImports.ARG_LONG_NAME].__name__}'."  # noqa: E501
    )


@pytest.fixture
def toml_dict_with_bad_field_types_and_error2():
    return {
        FollowImports.ARG_LONG_NAME: 3,
        ExcludeImports.ARG_LONG_NAME: [
            "a\\.b\\.c",
            "a\\.b.*",
            "a\\.b\\.c\\.e",
            "a\\.b\\.c.*",
        ],
        ExcludePatterns.ARG_LONG_NAME: ["a_.*", "b_.*", "_.*"],
        ShowWarnings.ARG_LONG_NAME: "all",
        ShowPath.ARG_LONG_NAME: "full",
        StrictOrPermissive.PERMISSIVE_ARG_LONG_NAME: 1,
        Output.SHOW_IR_ARG_LONG_NAME: 4,  # bad field type
        Output.SHOW_RESULTS_ARG_LONG_NAME: True,
        Output.SHOW_STATS_ARG_LONG_NAME: True,
        SaveResults.ARG_LONG_NAME: "rattr/cli/parser.py",
    }, (
        f"Error parsing pyproject.toml. Arg: '{Output.SHOW_IR_ARG_LONG_NAME}' "
        f"is of wrong type: 'int'. Expected type: "
        f"'{Output.TOML_ARG_NAME_ARG_TYPE_MAP[Output.SHOW_IR_ARG_LONG_NAME].__name__}'."
    )


@pytest.fixture
def toml_dict_with_bad_field_types_and_error3():
    return {
        FollowImports.ARG_LONG_NAME: 3,
        ExcludeImports.ARG_LONG_NAME: [
            "a\\.b\\.c",
            "a\\.b.*",
            "a\\.b\\.c\\.e",
            "a\\.b\\.c.*",
        ],
        ExcludePatterns.ARG_LONG_NAME: True,  # bad field type
        ShowWarnings.ARG_LONG_NAME: "all",
        ShowPath.ARG_LONG_NAME: "full",
        StrictOrPermissive.PERMISSIVE_ARG_LONG_NAME: 1,
        Output.SHOW_IR_ARG_LONG_NAME: True,
        Output.SHOW_RESULTS_ARG_LONG_NAME: True,
        Output.SHOW_STATS_ARG_LONG_NAME: True,
        SaveResults.ARG_LONG_NAME: "rattr/cli/parser.py",
    }, (
        f"Error parsing pyproject.toml. Arg: '{ExcludePatterns.ARG_LONG_NAME}' "
        f"is of wrong type: 'bool'. Expected type: "
        f"'{ExcludePatterns.TOML_ARG_NAME_ARG_TYPE_MAP[ExcludePatterns.ARG_LONG_NAME].__name__}'."  # noqa: E501
    )


@pytest.fixture
def toml_dicts_with_bad_field_types_and_errors(
    toml_dict_with_bad_field_types_and_error1,
    toml_dict_with_bad_field_types_and_error2,
    toml_dict_with_bad_field_types_and_error3,
):
    return [
        toml_dict_with_bad_field_types_and_error1,
        toml_dict_with_bad_field_types_and_error2,
        toml_dict_with_bad_field_types_and_error3,
    ]


@pytest.fixture
def toml_dict_with_mutex_arg_violation_and_error1():
    return {
        FollowImports.ARG_LONG_NAME: 3,
        ExcludeImports.ARG_LONG_NAME: [
            "a\\.b\\.c",
            "a\\.b.*",
            "a\\.b\\.c\\.e",
            "a\\.b\\.c.*",
        ],
        ExcludePatterns.ARG_LONG_NAME: ["a_.*", "b_.*", "_.*"],
        ShowWarnings.ARG_LONG_NAME: "all",
        ShowPath.ARG_LONG_NAME: "full",
        StrictOrPermissive.PERMISSIVE_ARG_LONG_NAME: 1,
        Output.SHOW_IR_ARG_LONG_NAME: True,  # mutex violation
        Output.SILENT_ARG_LONG_NAME: True,  # mutex violation
        SaveResults.ARG_LONG_NAME: "results.json",
    }, (
        f"-irs "
        f"('--{Output.SHOW_IR_ARG_LONG_NAME}', "
        f"'--{Output.SHOW_RESULTS_ARG_LONG_NAME}', "
        f"'--{Output.SHOW_STATS_ARG_LONG_NAME}') "
        f"and -S ('--{Output.SILENT_ARG_LONG_NAME}') are mutually exclusive"
    )


@pytest.fixture
def toml_dict_with_mutex_arg_violation_and_error2():
    return {
        FollowImports.ARG_LONG_NAME: 3,
        ExcludeImports.ARG_LONG_NAME: [
            "a\\.b\\.c",
            "a\\.b.*",
            "a\\.b\\.c\\.e",
            "a\\.b\\.c.*",
        ],
        ExcludePatterns.ARG_LONG_NAME: ["a_.*", "b_.*", "_.*"],
        ShowWarnings.ARG_LONG_NAME: "all",
        ShowPath.ARG_LONG_NAME: "full",
        StrictOrPermissive.STRICT_ARG_LONG_NAME: True,  # mutex violation
        StrictOrPermissive.PERMISSIVE_ARG_LONG_NAME: 1,  # mutex violation
        Output.SHOW_IR_ARG_LONG_NAME: True,
        Output.SHOW_RESULTS_ARG_LONG_NAME: True,
        Output.SHOW_STATS_ARG_LONG_NAME: True,
        SaveResults.ARG_LONG_NAME: "results.json",
    }, (
        f"argument --{StrictOrPermissive.PERMISSIVE_ARG_LONG_NAME}: not allowed "
        f"with argument --{StrictOrPermissive.STRICT_ARG_LONG_NAME}"
    )


@pytest.fixture
def toml_dicts_with_mutex_arg_violation_and_errors(
    toml_dict_with_mutex_arg_violation_and_error1,
    toml_dict_with_mutex_arg_violation_and_error2,
):
    return [
        toml_dict_with_mutex_arg_violation_and_error1,
        toml_dict_with_mutex_arg_violation_and_error2,
    ]


@pytest.fixture
def correct_toml_dict1():
    return {
        FollowImports.ARG_LONG_NAME: 3,
        ExcludeImports.ARG_LONG_NAME: [
            "a\\.a\\.a",
            "b\\.b.*",
            "c\\.c\\.c\\.c",
            "d\\d\\.d.*",
        ],
        ExcludePatterns.ARG_LONG_NAME: ["a_.*", "b_.*", "c_.*"],
        ShowWarnings.ARG_LONG_NAME: "all",
        StrictOrPermissive.STRICT_ARG_LONG_NAME: True,
        SaveResults.ARG_LONG_NAME: "results.json",
    }


@pytest.fixture
def correct_toml_dict2():
    return {
        FollowImports.ARG_LONG_NAME: 3,
        ExcludeImports.ARG_LONG_NAME: [
            "a\\.a\\.a",
            "b\\.b.*",
            "c\\.c\\.c\\.c",
            "d\\d\\.d.*",
        ],
        ExcludePatterns.ARG_LONG_NAME: ["a_.*", "b_.*", "c_.*"],
        ShowWarnings.ARG_LONG_NAME: "all",
        ShowPath.ARG_LONG_NAME: "full",
        StrictOrPermissive.PERMISSIVE_ARG_LONG_NAME: 1,
        SaveResults.ARG_LONG_NAME: "results.json",
    }


@pytest.fixture
def correct_toml_dict3():
    return {
        FollowImports.ARG_LONG_NAME: 1,
        ExcludeImports.ARG_LONG_NAME: [
            "a\\.b\\.c",
            "a\\.b.*",
            "a\\.b\\.c\\.e",
            "a\\.b\\.c.*",
        ],
        ShowWarnings.ARG_LONG_NAME: "all",
        ShowPath.ARG_LONG_NAME: "full",
        StrictOrPermissive.STRICT_ARG_LONG_NAME: True,
        Output.SHOW_IR_ARG_LONG_NAME: True,
        Output.SHOW_RESULTS_ARG_LONG_NAME: True,
        Output.SHOW_STATS_ARG_LONG_NAME: True,
        SaveResults.ARG_LONG_NAME: "results.json",
    }


@pytest.fixture
def sys_args1():
    return [
        "rattr",
        "rattr/cli/parser.py",
    ]


@pytest.fixture
def sys_args2():
    return [
        "rattr",
        "--follow-imports",
        "2",
        "--strict",
        "-w",
        "file",
        "rattr/cli/argparse.py",
        "-p",
        "short",
    ]


@pytest.fixture
def sys_args3():
    return [
        "rattr",
        "--follow-imports",
        "2",
        "--strict",
        "-w",
        "file",
        "rattr/cli/argparse.py",
        "-p",
        "short",
        "-F",
        "*exclude-import*",
        "-x",
        "*exclude-pattern*",
        "-S",
    ]


@pytest.fixture
def sys_args4():
    return ["rattr", "rattr/cli/parser.py", "-S"]


@pytest.fixture
def sys_args5():
    return ["rattr", "rattr/cli/parser.py", "--permissive", "3"]


@pytest.fixture
def sys_args6():
    here = Path(__file__).resolve().parent / "data" / "config_1.toml"

    return [
        "rattr",
        "rattr/cli/parser.py",
        "--permissive",
        "3",
        "--config",
        str(here),
    ]


@pytest.fixture
def walrus():
    def parse(expr: str):
        return ast.parse(f"a = ({expr})").body[0].value

    def _inner(*exprs):
        if len(exprs) == 0:
            raise ValueError

        if len(exprs) == 1:
            return parse(exprs[0])
        else:
            return [parse(e) for e in exprs]

    return _inner


@pytest.fixture
def stringify_nodes():
    def _inner(nodes: ast.AST):
        return [ast.dump(n) for n in nodes]

    return _inner
