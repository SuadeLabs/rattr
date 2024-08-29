"""Rattr analyser util functions."""
from __future__ import annotations

import ast
import builtins
import io
import re
import sys
from contextlib import redirect_stderr
from itertools import accumulate, chain, filterfalse
from pathlib import Path
from string import ascii_lowercase
from time import perf_counter
from typing import TYPE_CHECKING

from isort.api import place_module

from rattr import error
from rattr.analyser.exc import RattrResultsError
from rattr.ast.types import AstComprehensions, AstLiterals, AstNodeWithName
from rattr.config import Config
from rattr.extra import DictChanges  # noqa: F401
from rattr.models.ir import FunctionIr
from rattr.models.symbol import (
    PYTHON_ATTR_ACCESS_BUILTINS,
    PYTHON_BUILTINS,
    Call,
    CallArguments,
    Class,
    Import,
    Name,
)
from rattr.module_locator.util import find_module_spec_fast

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from typing import Any, Final, Type

    from rattr.analyser.types import RattrResults
    from rattr.ast.types import Identifier
    from rattr.models.context import Context
    from rattr.models.symbol import Symbol


re_rattr_name: Final = re.compile(r"^[A-Za-z_][\w\(\)\[\]\.]*$")


def get_basename_fullname_pair(
    node: ast.expr,
    safe: bool = False,
) -> tuple[str, str]:
    """Return the node's tuple of the basename and the fullname.

    If node (and it's children, recursively) are not StrictlyNameable, then a
    true name cannot be produced. If safe=True, then an attempt is made:

    #### All StrictlyNameable

        >>> get_basename_fullname_pair(
        ...     ast.parse("a.b[0].attr").body[0].value,
        ...     safe=True # or False
        ... )
        "a.b[].attr"

    #### Not all-StrictlyNameable, unsafe

        >>> get_basename_fullname_pair(
        ...     ast.parse("(a, b)[0].attr").body[0].value,
        ...     safe=False
        ... )
        error.RattrLiteralInNameable: ...

    #### Not all-StrictlyNameable, safe

        >>> get_basename_fullname_pair(
        ...     ast.parse("(a, b)[0].attr").body[0].value,
        ...     safe=True
        ... )
        "@Tuple[].attr"

    For the third example, the fact that `a.attr` is accessed is lost!

    NOTE Deprecated, see rattr.ast.util.names_of

    """
    config = Config()

    # Base case
    # ast.Name ⊂ StrictlyNameable
    if isinstance(node, ast.Name):
        return node.id, node.id

    # Recursive case
    # node ⊂ ( StrictlyNameable \ { ast.Name } )
    if isinstance(node, ast.Call):
        basename, sub_name = get_basename_fullname_pair(node.func, safe)
    elif isinstance(node, AstNodeWithName):
        basename, sub_name = get_basename_fullname_pair(node.value, safe)

    if isinstance(node, ast.Attribute):
        return basename, f"{sub_name}.{node.attr}"

    if isinstance(node, ast.Subscript):
        return basename, f"{sub_name}[]"

    if isinstance(node, ast.Call):
        if any(is_call_to(attr, node) for attr in PYTHON_ATTR_ACCESS_BUILTINS):
            return basename, ".".join(get_xattr_obj_name_pair(basename, node))

        return basename, f"{sub_name}()"

    if isinstance(node, ast.Starred):
        return basename, f"*{sub_name}"

    # Error case
    # node ⊂ Nameable ^ node ⊄ StrictlyNameable
    if safe:
        return (
            f"{config.LITERAL_VALUE_PREFIX}{node.__class__.__name__}",
            f"{config.LITERAL_VALUE_PREFIX}{node.__class__.__name__}",
        )

    _error_class: Type[TypeError] = TypeError
    if isinstance(node, ast.UnaryOp):
        _error_class = error.RattrUnaryOpInNameable
    elif isinstance(node, ast.BinOp):
        _error_class = error.RattrBinOpInNameable
    elif isinstance(node, ast.Constant):
        _error_class = error.RattrConstantInNameable
    elif isinstance(node, AstLiterals):
        _error_class = error.RattrLiteralInNameable
    elif isinstance(node, AstComprehensions):
        _error_class = error.RattrComprehensionInNameable
    elif isinstance(node, ast.GeneratorExp):
        _error_class = error.RattrComprehensionInNameable
    else:
        _error_class = TypeError

    raise _error_class(f"line {node.lineno}: {ast.dump(node)}")


def get_basename(node: ast.expr, safe: bool = False) -> str:
    """Return the `_identifier` of the innermost ast.Name node.

    NOTE Deprecated, see rattr.ast.utils
    """
    return get_basename_fullname_pair(node, safe)[0]


def get_fullname(node: ast.expr, safe: bool = False) -> str:
    """Return the fullname of the given node.

    NOTE Deprecated, see rattr.ast.utils
    """
    return get_basename_fullname_pair(node, safe)[1]


def get_attrname(node: ast.expr) -> str:
    """Return the `_identifier` of the outermost attribute in a nested name.

    E.g. `a.b.c.d` -> `d`
    >>> attr = ast.parse("object.attribute").body[0].value
    """
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        return node.attr

    if isinstance(node, ast.Call):
        return get_attrname(node.func)

    raise TypeError(f"line {node.lineno}: {ast.dump(node)}")


def unravel_names(
    node: ast.expr,
    *,
    get_name: Callable[[ast.expr], str] = get_basename,
) -> Iterable[str]:
    """Return the basename of each nameable in the given node.

    >>> ravelled_names = ast.parse("a, b = 1, 2").body[0].targets[0]
    >>> list(unravel_names(ravelled_names))
    ["a", "b"]

    >>> ravelled_names = ast.parse("(a, b), c, d.e = ...").body[0].targets[0]
    >>> list(unravel_names(ravelled_names))
    ["a", "b", "c", "d"]

    The name getter can be overridden for example as `get_fullname`:
    >>> ravelled_names = ast.parse("a.attr = 1").body[0].targets[0]
    >>> list(unravel_names(ravelled_names))
    ["a"]
    >>> list(unravel_names(ravelled_names, get_name=get_fullname))
    ["a.attr"]

    NOTE Deprecated, see rattr.ast.util.unravel_names

    """
    if isinstance(node, AstNodeWithName):
        return [get_name(node)]

    if isinstance(node, (ast.Tuple, ast.List)):
        ravelled = [unravel_names(i, get_name=get_name) for i in node.elts]
        return chain.from_iterable(ravelled)

    raise TypeError(f"line {node.lineno}: {ast.dump(node)}")


def is_call_to(target: str, node: ast.Call) -> bool:
    """Return `True` if the given node is a __direct__ call to `target`.

    In the case `getattr(o, a).some_call()`, the basename of `.some_call()` is
    `getattr` -- this is the correct basename but gives incorrect behaviour;
    the args of `getattr` are not properly resolved and `.some_call()` is not
    fully visited.

    Thus rather than determining if a call is to `getattr` by checking the
    basename against "getattr", use `is_call_to("getattr", node)`.

    NOTE Deprecated, see rattr.ast.utils

    """
    if not isinstance(node, ast.Call):
        raise TypeError(f"line {node.lineno}: {ast.dump(node)}")

    if not isinstance(node.func, ast.Name):
        return False

    return node.func.id == target


def has_affect(builtin: str) -> bool:
    """Return `True` if the given builtin can affect accessed attributes."""
    if builtin not in PYTHON_BUILTINS:
        raise ValueError(f"'{builtin}' is not a Python builtin")

    return builtin in PYTHON_ATTR_ACCESS_BUILTINS


def get_xattr_obj_name_pair(
    xattr: str,
    node: ast.Call,
    warn: bool = False,
) -> tuple[str, str]:
    """Return the object-name pair for a call to getattr, setattr, etc.

    NOTE Deprecated, see rattr.ast.utils
    """
    if len(node.args) < 2:
        error.fatal(f"invalid call to '{xattr}', not enough args", node)

    this = f"'{xattr}'"
    obj, attr = node.args[0], node.args[1]

    # NOTE Only warn if told to, avoids repeated warnings
    if warn and not isinstance(attr, ast.Str):
        error.error(f"{this} expects name to be a string literal", node)

    if isinstance(attr, ast.Str):
        attr_name = attr.s
    else:
        attr_name = f"<{get_fullname(attr, safe=True)}>"

    # Nested calls must be to the same function
    if isinstance(obj, ast.Call) and not is_call_to(xattr, obj):
        error.fatal(f"{this} object must be a name or a call to {this}", node)

    # Recurive Case
    # E.g. `getattr(getattr(a, 'b'), 'c')`
    if isinstance(obj, ast.Call):
        return ".".join(get_xattr_obj_name_pair(xattr, obj)), attr_name

    # Base Case
    # NOTE Call ∈ AstStrictlyNameable, thus base case comes second
    if isinstance(obj, AstNodeWithName):
        return get_fullname(node.args[0]), attr_name

    raise TypeError(f"line {node.lineno}: {ast.dump(node)}")


def get_decorator_name(decorator: ast.expr) -> str:
    """Return name of the given decorator.."""
    if not isinstance(decorator, (ast.Name, ast.Attribute, ast.Call)):
        raise TypeError("Decorator must be an ast.Name, ast.Attribute, or ast.Call")

    return get_basename(decorator)


def get_nth_argument_name(arguments: ast.arguments, n: int) -> str:
    """Return the name of the nth positional argument, or Ɛ if out-of-range."""
    _arguments = arguments.args

    if len(_arguments) == 0:
        return ""

    if not (0 <= n < len(_arguments)):
        return ""

    return _arguments[n].arg


def get_first_argument_name(arguments: ast.arguments) -> str:
    return get_nth_argument_name(arguments, 0)


def get_second_argument_name(arguments: ast.arguments) -> str:
    return get_nth_argument_name(arguments, 1)


def has_annotation(
    name: str,
    target: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> bool:
    """Return `True` if the function is decorated with the given annotation."""
    return name in map(get_attrname, target.decorator_list)


def get_annotation(
    name: str,
    target: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> ast.expr | None:
    """Return the decorator node for the given annotation on the function."""
    matching: list[ast.expr] = []

    for decorator in target.decorator_list:
        suffix = get_attrname(decorator)

        if suffix != name:
            continue

        matching.append(decorator)

    if len(matching) < 1:
        return None
    if len(matching) > 1:
        error.fatal(
            f"duplicated annotation {name!r} on {target.name!r}",
            culprit=target,
        )

    return matching[0]


def safe_eval(expr: ast.expr, culprit: ast.AST) -> Any | None:
    """Return the given expression as evaluated at compile-time.

    NOTE
        Use this instead of Python's `eval` to avoid potential arbitrary code
        execution.

    """
    _error = "unable to evaluate {} at compile-time"

    if isinstance(expr, ast.Num):
        return expr.n

    if isinstance(expr, (ast.Str, ast.Bytes)):
        return expr.s

    if isinstance(expr, ast.NameConstant):
        return expr.value

    if isinstance(expr, ast.List):
        return [safe_eval(e, culprit) for e in expr.elts]

    if isinstance(expr, ast.Tuple):
        return tuple([safe_eval(e, culprit) for e in expr.elts])

    if isinstance(expr, ast.Set):
        return set([safe_eval(e, culprit) for e in expr.elts])

    if isinstance(expr, ast.Dict):
        if not all(k is not None for k in expr.keys):
            return error.fatal(_error.format("dictionary unpacking"), culprit)

        keys = map(lambda k: safe_eval(k, culprit), expr.keys)
        values = map(lambda v: safe_eval(v, culprit), expr.values)

        return {k: v for k, v in zip(keys, values)}

    return error.fatal(_error.format(f"'{ast.dump(expr)}'"), culprit)


def parse_annotation(
    name: str,
    fn_def: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> tuple[list[Any], dict[str, Any]]:
    """Return the positional and keyword arguments of the annotation."""
    annotation = get_annotation(name, fn_def)

    pos_args: list[Any] = []
    named_args: dict[str, Any] = {}

    if not annotation:
        return pos_args, named_args

    if not isinstance(annotation, ast.Call):
        return pos_args, named_args

    for arg in annotation.args:
        pos_args.append(safe_eval(arg, fn_def))

    for kwarg in annotation.keywords:
        named_args[kwarg.arg] = safe_eval(kwarg.value, fn_def)

    return pos_args, named_args


def is_name(target: str | object) -> bool:
    """Return `True` if the given name is a valid Python identifier."""
    if not isinstance(target, str):
        return False

    name = target.removeprefix("*").removeprefix("@")
    return re_rattr_name.fullmatch(name) is not None


def is_set_of_names(target: set[str] | object) -> bool:
    return isinstance(target, set) and all(is_name(name) for name in target)


def is_list_of_names(target: list[str] | object) -> bool:
    return isinstance(target, list) and all(is_name(name) for name in target)


def is_list_of_call_specs(
    call_specs: list[tuple[Identifier, tuple[list[Identifier], dict[Identifier, str]]]]
    | object,
) -> bool:
    if not isinstance(call_specs, list):
        return False

    for spec in call_specs:
        if not isinstance(spec, tuple):
            return False

        if len(spec) != 2:
            return False

        target_name, target_args = spec

        if not is_name(target_name):
            return False

        if not isinstance(target_args, tuple):
            return False

        if len(target_args) != 2:
            return False

        target_pos_args, target_keyword_args = target_args

        if not is_list_of_names(target_pos_args):
            return False

        for arg_name, local_identifier in target_keyword_args.items():
            if not is_name(arg_name):
                return False
            if not is_name(local_identifier):
                return False

    return True


def validate_rattr_results(rattr_results: RattrResults) -> None:
    """Raise a RattrResultsError if the given results are invalid.

    Raises:
        RattrResultsError: The given rattr results are invalid.
    """
    for key in ("gets", "sets", "dels"):
        if not is_set_of_names(rattr_results[key]):
            raise RattrResultsError(
                f"'rattr_results' expects a set[Identifier] for {key!r}, where "
                f"Identifier is a type alias for str"
            )

    if not is_list_of_call_specs(rattr_results["calls"]):
        raise RattrResultsError(
            "'rattr_results' expects 'calls' to be a "
            "list[tuple[TargetName, tuple[list[PositionalArgumentName], "
            "dict[KeywordArgumentName, LocalIdentifier]]]]; "
            "where TargetName, PositionalArgumentName, KeywordArgumentName, and "
            "LocalIdentifier are type aliases for str"
        )


def parse_rattr_results_from_annotation_args_impl(
    fn_def: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> RattrResults:
    stderr_stream = io.StringIO()
    has_likely_missing_comma = False

    try:
        with redirect_stderr(stderr_stream):
            decorator_args, decorator_kwargs = parse_annotation("rattr_results", fn_def)
    except SystemExit as exc:
        stderr = stderr_stream.getvalue()

        # TODO On switching to proper logging use logger here
        for line in stderr.splitlines():
            if "unable to evaluate" in line:
                has_likely_missing_comma = True
            else:
                print(line)

        if has_likely_missing_comma:
            error.fatal(
                "unable to parse 'rattr_results', you are likely missing a "
                "comma in 'calls'",
                culprit=fn_def,
            )

        raise exc

    if decorator_args != []:
        error.fatal(
            f"unexpected positional arguments to 'rattr_results'; expected "
            f"none, got {decorator_args}",
            culprit=fn_def,
        )

    rattr_results_from_annotation: RattrResults = {
        "gets": set(),
        "sets": set(),
        "dels": set(),
        "calls": list(),
    }
    for key, results in decorator_kwargs.items():
        if key not in rattr_results_from_annotation:
            continue
        rattr_results_from_annotation[key] = results

    if decorator_kwargs.keys() - rattr_results_from_annotation.keys():
        error.fatal(
            f"unexpected keyword arguments to 'rattr_results'; expected any of "
            f"{list(rattr_results_from_annotation.keys())}, got "
            f"{list(decorator_kwargs.keys())}",
            culprit=fn_def,
        )

    return rattr_results_from_annotation


def parse_rattr_results_from_annotation(
    fn_def: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    *,
    context: Context,
) -> FunctionIr:
    """Return the IR for the given function, assuming it is annotated."""
    rattr_results = parse_rattr_results_from_annotation_args_impl(fn_def)

    try:
        validate_rattr_results(rattr_results)
    except RattrResultsError as exc:
        error.fatal(exc.message, culprit=fn_def)

    def as_name(name: Identifier) -> Name:
        return Name(
            name=name,
            basename=name.replace("*", "").split(".")[0],
            token=fn_def,
        )

    def as_call(
        call: tuple[Identifier, tuple[list[Identifier], dict[Identifier, Identifier]]],
    ) -> Call:
        (target_name, (args, kwargs)) = call
        return Call(
            name=target_name,
            args=CallArguments(args=args, kwargs=kwargs),
            target=context.get_call_target(target_name, culprit=fn_def),
            token=fn_def,
        )

    return {
        "gets": {as_name(name) for name in rattr_results["gets"]},
        "sets": {as_name(name) for name in rattr_results["sets"]},
        "dels": {as_name(name) for name in rattr_results["dels"]},
        "calls": {as_call(call) for call in rattr_results["calls"]},
    }


def is_blacklisted_module(module: str) -> bool:
    """Return `True` if the given module matches a blacklisted pattern.

    NOTE Deprecated, see rattr.module_locator.util.is_in_import_blacklist
    """
    config = Config()

    # Exclude stdlib modules such as the built-in "_thread"
    if is_stdlib_module(module):
        return False

    return any(re.fullmatch(p, module) for p in config.blacklist_patterns)


def is_pip_module(module: str) -> bool:
    """Return `True` if the given module is pip installed.

    NOTE Deprecated, see rattr.ast.place
    """
    pip_install_locations = (".+/site-packages.*",)

    spec = find_module_spec_fast(module)

    if spec is None or spec.origin is None:
        return False

    return any(
        re.fullmatch(
            pip_install_location,
            # No backslashes, bad windows!
            spec.origin.replace("\\", "/"),
        )
        for pip_install_location in pip_install_locations
    )


def is_stdlib_module(module: str) -> bool:
    """Return `True` if the given module is in the Python standard library.

    >>> is_stdlib_module("math")
    True

    >>> is_stdlib_module("math.pi")
    True

    NOTE Deprecated, see rattr.ast.place
    """
    return place_module(module) == "STDLIB"


def is_in_builtins(name_or_qualified_name: str) -> bool:
    return name_or_qualified_name in dir(builtins)


class timer:
    """Context manager to return the context's elapsed time in seconds."""

    def __enter__(self):
        self.start = perf_counter()
        self.end = 0.0
        return self

    def __exit__(self, *_):
        self.end = perf_counter()

    @property
    def time(self):
        return self.end - self.start


class read:
    """Context manager to return file contents and the number of lines."""

    def __init__(self, file: Path | str) -> None:
        self.file = file

    def __enter__(self) -> tuple[int, str]:
        with open(self.file, "r") as f:
            lines = f.readlines()
        return len(lines) + 1, "".join(lines)

    def __exit__(self, *_) -> None:
        pass


def get_starred_imports(
    symbols: list[Symbol],
    seen: Iterable[Import],
) -> list[Import]:
    """Return the starred imports in the given symbols."""
    starred: list[Import] = []

    for symbol in symbols:
        if not isinstance(symbol, Import):
            continue

        if symbol.name != "*":
            continue

        if symbol in seen:
            continue

        starred.append(symbol)

    return starred


def get_function_body(
    node: ast.Lambda | ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.stmt]:
    """Return the body of the given function as a list of statements."""
    if isinstance(node, ast.Lambda):
        return [node.body]

    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.body

    raise TypeError(f"line {node.lineno}: {ast.dump(node)}")


def get_assignment_targets(
    node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
) -> list[ast.expr]:
    """Return the given assignment's targets as a list."""
    if isinstance(node, ast.Assign):
        return node.targets

    if isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
        return [node.target]

    raise TypeError(f"line {node.lineno}: {ast.dump(node)}")


def get_contained_walruses(
    node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
) -> list[ast.NamedExpr]:
    """Return the walruses in the RHS of the given assignment.

    >>> get_nested_walruses(ast.parse("a = (b := c)"))
    [NamedExpr(target=Name(id='b', ctx=Store()), value=Name(id='c', ctx=Load())), ]

    >>> get_nested_walruses(ast.parse("a = (b, c := d)"))
    [NamedExpr(target=Name(id='c', ctx=Store()), value=Name(id='d', ctx=Load())), ]
    """
    if not walrus_in_rhs(node):
        return list()

    if isinstance(node.value, (ast.Tuple, ast.List)):
        rhs_values = node.value.elts
    else:
        rhs_values = [node.value]

    return list(filter(lambda v: isinstance(v, ast.NamedExpr), rhs_values))


def assignment_is_one_to_one(
    node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
) -> bool:
    """Return `True` if the given assignment is one-to-one.

    NOTE Deprecated, see rattr.ast.util.assignment_is_one_to_one
    """
    _iterable = (ast.Tuple, ast.List)

    targets = get_assignment_targets(node)

    # Ensure LHS is singular
    if len(targets) > 1 or any(isinstance(t, _iterable) for t in targets):
        return False

    return not isinstance(node.value, _iterable)


def lambda_in_rhs(
    node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
) -> bool:
    """Return `True` if the RHS of the given assignment contains a lambda.

    NOTE Deprecated, see rattr.ast.util.has_lambda_in_rhs
    """
    _iterable = (ast.Tuple, ast.List)

    if isinstance(node.value, ast.Lambda):
        return True
    elif isinstance(node.value, _iterable):
        return any(isinstance(v, ast.Lambda) for v in node.value.elts)
    else:
        return False


def walrus_in_rhs(
    node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
) -> bool:
    """Return `True` if the RHS contains a walrus operator.

    NOTE Deprecated, see rattr.ast.util.has_walrus_in_rhs
    """
    _iterable = (ast.Tuple, ast.List)

    if isinstance(node.value, ast.NamedExpr):
        return True
    elif isinstance(node.value, _iterable):
        return any(isinstance(v, ast.NamedExpr) for v in node.value.elts)
    else:
        return False


def namedtuple_in_rhs(
    node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
) -> bool:
    """Return `True` if the RHS contains a namedtuple creation.

    NOTE Deprecated, see rattr.ast.util.has_namedtuple_declaration_in_rhs
    """
    _iterable = (ast.Tuple, ast.List)

    def _target_is_namedtuple(call: ast.Call) -> bool:
        # HACK
        #   This is a naive approach, when enum / class-namedtuple / etc detection is
        #   refactored we can do this a bit better.
        #   See: cls.py::is_enum, cls.py::is_namedtuple
        name = get_fullname(call.func, safe=True)
        return name == "namedtuple" or name.endswith(".namedtuple")

    if isinstance(node.value, ast.Call):
        return _target_is_namedtuple(node.value)
    elif isinstance(node.value, _iterable):
        return any(
            _target_is_namedtuple(value)
            for value in node.value.elts
            if isinstance(value, ast.Call)
        )
    else:
        return False


def _attrs_from_list_of_strings(attrs_argument: ast.List) -> list[str]:
    """NOTE Deprecated, see rattr.ast.util.unpack_ast_list_of_strings."""
    attrs: list[str] = [
        arg.value
        for arg in attrs_argument.elts
        if isinstance(arg, ast.Constant)
        if isinstance(arg.value, str)
    ]

    if len(attrs) != len(attrs_argument.elts):
        raise SyntaxError

    return attrs


def _attrs_from_space_delimited_string(attrs_argument: ast.Constant) -> list[str]:
    """NOTE Deprecated, see rattr.ast.util.parse_space_delimited_ast_string."""
    if not isinstance(attrs_argument.value, str):
        raise SyntaxError

    attrs = attrs_argument.value.split(" ")

    if not all(attr.isidentifier() for attr in attrs):
        raise SyntaxError

    return attrs


def _namedtuple_attrs_from_second_argument(attrs_argument: ast.AST) -> list[str]:
    """NOTE Deprecated."""
    if isinstance(attrs_argument, ast.List):
        return _attrs_from_list_of_strings(attrs_argument)

    if isinstance(attrs_argument, ast.Constant):
        return _attrs_from_space_delimited_string(attrs_argument)

    raise SyntaxError


def get_namedtuple_attrs_from_call(
    node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
) -> tuple[list[str], dict[str, str]]:
    """Return the args/attrs of the namedtuple constructed by this assignment by call.

    #### Note
    Assumes one-to-one assignment.

    #### Examples
    >>> node = ast.parse("p = namedtuple('p', ['x', 'y'])").body[0].value
    >>> get_namedtuple_init_signature_from_assignment(node)
    ["self", "x", "y]

    Raises:
        TypeError: The node is not an assignment of a call.

    Returns:
        tuple[list[str], dict[str, str]]: The positional and keyword args of the init.

    NOTE Deprecated, see rattr.ast.util.namedtuple_init_signature_from_declaration
    """
    _invalid_signature_error = (
        "namedtuple expects exactly two positional arguments (i.e. name, attrs)"
    )
    _invalid_second_parameter_value_error = (
        "namedtuple expects the second positional argument to be a list of valid "
        "identifiers as either a list of string-literals or a space-delimited "
        "string-literal"
    )

    # Parse call arguments
    if not isinstance(node.value, ast.Call):
        raise TypeError

    namedtuple_call_arguments = node.value.args

    if len(namedtuple_call_arguments) != 2:
        error.fatal(_invalid_signature_error, culprit=node.value)

    _, namedtuple_attrs_argument = namedtuple_call_arguments

    try:
        attrs = _namedtuple_attrs_from_second_argument(namedtuple_attrs_argument)
    except SyntaxError:
        error.fatal(_invalid_second_parameter_value_error, culprit=node.value)

    return ["self", *attrs]


def class_in_rhs(
    node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
    context: Context,
) -> bool:
    """Return `True` if the RHS of the given assignment is a class init."""
    _iterable = (ast.Tuple, ast.List)

    def expr_is_class(expr):
        full = get_fullname(expr, safe=True)

        try:
            target = context.get_call_target(full, expr, warn=False)
        except ValueError:
            return False

        return isinstance(target, Class)

    if isinstance(node.value, ast.Call):
        return expr_is_class(node.value)
    elif isinstance(node.value, _iterable):
        return any(expr_is_class(e) for e in node.value.elts)
    else:
        return False


def is_starred_import(node: ast.Import | ast.ImportFrom) -> bool:
    """Return `True` if the given import is a `from module import *`.

    NOTE Deprecated, see rattr.ast.util.is_starred_import
    """
    if not isinstance(node, ast.ImportFrom):
        return False

    return any(target.name == "*" for target in node.names)


def is_relative_import(node: ast.Import | ast.ImportFrom) -> bool:
    """Return `True` if the given import is a relative import.

    NOTE Deprecated, see rattr.ast.util.is_relative_import
    """
    if not isinstance(node, ast.ImportFrom):
        return False

    return node.level != 0


def module_name_from_file_path(file: Path | str | None) -> str | None:
    """Return the recognised name of the given module.

    NOTE Deprecated, see rattr.module_locator.util.derive_module_name_from_path
    """
    if file is None:
        raise ValueError

    if isinstance(file, Path):
        file = str(file)

    module = file.replace("/", ".").replace("\\", ".")

    if module.endswith(".__init__.py"):
        module = module[:-12]

    if module.endswith(".py"):
        module = module[:-3]

    module = module.strip(".")

    # Get possible module names in relevancy order
    parts = module.split(".")
    dotted_parts = list(chain.from_iterable(zip(parts, ["."] * len(parts))))
    possible = list(accumulate(reversed(dotted_parts), lambda p0, p1: f"{p1}{p0}"))
    well_formed = list(filterfalse(lambda p: p.startswith("."), possible))
    well_formed = list(wf[:-1] for wf in well_formed if len(wf) >= 1)
    ordered = list(reversed(well_formed))

    for p in [*ordered, None]:
        if find_module_spec_fast(p) is None:
            break

    return p


def get_absolute_module_name(base: str, level: int, target: str) -> str:
    """Return the absolute import for the given relative import."""
    config = Config()

    if config.state.current_file.name == "__init__.py":
        level -= 1

    if level > 0:
        new_base = ".".join(base.split(".")[:-level])
    else:
        new_base = base

    return f"{new_base}.{target}"


def get_function_form(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Return the string representing the function form.

    Given the function, fn:
        ```
        def fn(a, b, c=None, *args, **kwargs):
            # ...
        ```

    The form is:
        `fn(a, b, c, *args, **kwargs)`

    """
    arguments = [a.arg for a in node.args.args]

    if node.args.vararg is not None:
        arguments.append(f"*{node.args.vararg.arg}")

    if node.args.kwarg is not None:
        arguments.append(f"**{node.args.kwarg.arg}")

    return f"'{node.name}({', '.join(arguments)})'"


def is_excluded_name(name: str) -> bool:
    """Return `True` if the given name is in the exclude list."""
    config = Config()
    return any(
        pattern.fullmatch(name) is not None
        for pattern in config.arguments.re_excluded_names
    )


def is_method_on_constant(name: str) -> bool:
    """Return `True` if the name is a call to method on a constant."""
    if sys.version_info.major == 3 and sys.version_info.minor <= 7:
        return name.startswith(
            (
                "@Num.",
                "@Str.",
                "@Bytes.",
                "@NameConstant.",
            )
        )

    if sys.version_info.major == 3 and sys.version_info.minor >= 8:
        return name.startswith("@Constant.")

    raise NotImplementedError


def is_method_on_cast(name: str) -> bool:
    """Return `True` if the name is a call to a method on a cast."""
    # NOTE All builtin functions return primitives (often `None`), ...
    builtins = {b for b in PYTHON_BUILTINS if b.startswith((*ascii_lowercase,))}

    # NOTE ... with the following exceptions
    builtins = builtins.difference(
        {
            "eval",
            "exec",
            "getattr",
            "iter",
            "next",
            "slice",
            "super",
            "type",
        }
    )

    # NOTE
    #   Direct call to `<primitive_returner>.method_name()`, do not allow call
    #   to call, etc because one may return non-primitive
    patterns = tuple((f"{b}\\(\\)\\.[^\\(\\)\\[\\]\\.]+" for b in builtins))

    return any(re.fullmatch(p, name) for p in patterns)


def is_method_on_primitive(name: str) -> bool:
    """Return `True` if the given name is a method on a primitive type."""
    if is_method_on_constant(name):
        return True

    if is_method_on_cast(name):
        return True

    return False


def get_dynamic_name(fn_name: str, node: ast.Call, pattern: str) -> Name:
    """Return the `Name` of the given pattern constructed from the call.

    Where first is the resolved name of the first call argument, and second is
    the resolved name of the second call argument.

    Assumes that the first argument is a variable (or nested call) and the
    second argument is a string -- names are resolved as such.

    Allows nested calls to functions with the same name (i.e. `name`).

    >>> call = ast.parse("getattr(object, 'attribute')").body[0].value
    >>> get_dynamic_name("getattr", call, "{first}.{second}")
    Name("object.attribute", "object")

    >>> call = ast.parse("getattr(getattr(a, 'b'), 'c')").body[0].value
    >>> get_dynamic_name("getattr", call, "{first}.{second}")
    Name("a.b.c", "a")

    >>> call = ast.parse("getattr(another_fn(a, 'b'), 'c')").body[0].value
    >>> get_dynamic_name("getattr", call, "{first}.{second}")
    sys.exit(1)

    >>> call = ast.parse("get_sub_attr(obj, 'attr')").body[0].value
    >>> get_dynamic_name("get_sub_attr", call, "{first}.sub.{second}")
    Name("obj.sub.attr", "obj")

    >>> call = ast.parse("get_sub_attr(get_sub_attr(o, 'in'), 'out')").body[0].value
    >>> get_dynamic_name("get_sub_attr", call, "{first}.mid.{second}")
    Name("o.in.mid.out", "o")

    >>> call = ast.parse("get_sub(obj)").body[0].value
    >>> get_dynamic_name("get_sub", call, "{first}.sub")
    Name("obj.sub", "obj")

    """
    first, second = get_xattr_obj_name_pair(fn_name, node, warn=True)
    basename = first.split(".")[0].replace("*", "").replace("[]", "").replace("()", "")

    return Name(
        name=pattern.format(first=first, second=second),
        basename=basename,
        token=node,
    )
