from __future__ import annotations

import ast
import sys
from contextlib import contextmanager
from importlib.util import find_spec
from os.path import dirname, join
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from rattr.analyser.base import CustomFunctionAnalyser, CustomFunctionHandler
from rattr.analyser.context import Context, RootContext
from rattr.analyser.context.symbol import Builtin, Call, Name, Symbol
from rattr.analyser.file import FileAnalyser
from rattr.analyser.results import generate_results_from_ir
from rattr.analyser.types import FileIr, FunctionIr
from rattr.analyser.util import LOCAL_VALUE_PREFIX, has_affect
from rattr.ast.types import AstFunctionDef
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
    config.addinivalue_line("markers", "windows: mark test to run only under Windows")
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

    if not is_windows():
        skip_test_items_with_mark(items, "windows")

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


def is_windows():
    return sys.platform == "win32"


@pytest.fixture(scope="session", autouse=True)
@mock.patch("rattr.config._types.validate_arguments", lambda args: args)
def _init_testing_config():
    Config(
        arguments=Arguments(
            pyproject_toml_override=None,
            _follow_imports_level=1,
            _excluded_imports=set(),
            _excluded_names=set(),
            _warning_level="default",
            collapse_home=True,
            truncate_deep_paths=True,
            is_strict=False,
            threshold=0,
            stdout=Output.results,
            target=Path("target.py"),
        ),
        state=State(),
    )


def _nth_line_is_empty(lines: list[str], *, n: int) -> bool:
    return lines and (lines[n] == "" or lines[n].isspace())


@pytest.fixture
def parse():
    def _inner(source: str) -> ast.AST:
        """Return the parsed AST for the given code, use relative indentation.

        Assumed usage is:
            parse(
                '''
                <source code>       # first line sets the base indent
                <source code>
                    <source code>   # this is indented once (relative)
                <source code>
                '''
            )

        """
        lines = source.splitlines()

        # Skip the first and last line if empty, this is because in the usage such as:
        # parse(
        #   """
        #   ...
        #   """
        # )
        # the first and last line (specifically the first) will have a different
        # indentation level, which will throw off `dedent(...)`.
        if _nth_line_is_empty(lines, n=0):
            lines = lines[1:]
        if _nth_line_is_empty(lines, n=-1):
            lines = lines[:-1]

        if not len(lines):
            raise ValueError("parse(...) expects a non-empty, non-whitespace string")

        return ast.parse(dedent("\n".join(lines)))

    return _inner


@pytest.fixture
def parse_with_context(parse: Callable[[str], ast.AST]):
    def _inner(source: str) -> tuple[ast.AST, Context]:
        _ast = parse(source)
        _ctx = RootContext(_ast)
        return _ast, _ctx

    return _inner


@pytest.fixture
def analyse_single_file(
    parse_with_context: Callable[[str], tuple[ast.AST, Context]],
) -> Callable[[str], tuple[FileIr, FileResults]]:
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
def platform_formatted_str():
    def _format_path_as_platform_specific_path(path: Path | str) -> str:
        # On Windows this should give:
        #   path_as_str("foo/bar.py") == path_as_str("foo\\bar.py") == "foo\\bar.py"
        # On Linux, MacOS, etc:
        #   path_as_str("foo/bar.py") == "foo/bar.py"
        return str(Path(path))

    return _format_path_as_platform_specific_path


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
def arguments():
    @contextmanager
    def _inner(**kwargs):
        arguments = Config().arguments

        _missing_attrs = {
            attr for attr in kwargs.keys() if not hasattr(arguments, attr)
        }
        if _missing_attrs:
            raise AttributeError(_missing_attrs)

        previous = {attr: getattr(arguments, attr) for attr in kwargs.keys()}

        for attr, value in kwargs.items():
            setattr(arguments, attr, value)

        yield

        for attr, value in previous.items():
            setattr(arguments, attr, value)

    return _inner


@pytest.fixture
def state():
    @contextmanager
    def _inner(**kwargs):
        state = Config().state

        _missing_attrs = {attr for attr in kwargs.keys() if not hasattr(state, attr)}
        if _missing_attrs:
            raise AttributeError(_missing_attrs)

        previous = {attr: getattr(state, attr) for attr in kwargs.keys()}

        for attr, value in kwargs.items():
            setattr(state, attr, value)

        yield

        for attr, value in previous.items():
            setattr(state, attr, value)

    return _inner


@pytest.fixture
def config():
    return Config()


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
        file_ir = FileIr(ctx)
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

    def on_def(self, name: str, node: AstFunctionDef, ctx: Context) -> FunctionIr:
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

    def on_call(self, name: str, node: ast.Call, ctx: Context) -> FunctionIr:
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

    def on_def(self, name: str, node: AstFunctionDef, ctx: Context) -> FunctionIr:
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

    def on_call(self, name: str, node: ast.Call, ctx: Context) -> FunctionIr:
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
