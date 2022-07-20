"""Rattr analyser util functions."""

import ast
import builtins
import hashlib
import json
import re
import sys
from contextlib import contextmanager
from copy import deepcopy
from importlib.util import find_spec
from itertools import accumulate, chain, filterfalse
from os.path import isfile
from string import ascii_lowercase
from time import perf_counter
from typing import (
    Any,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)

from isort import place_module

from rattr import config, error
from rattr.analyser.context.symbol import get_possible_module_names  # noqa
from rattr.analyser.context.symbol import (
    Class,
    Import,
    Name,
    Symbol,
    parse_call,
    parse_name,
)
from rattr.analyser.types import (
    AnyAssign,
    AnyFunctionDef,
    AstDef,
    Comprehension,
    Constant,
    FileResults,
    FuncOrAsyncFunc,
    FunctionIR,
    Literal,
    Nameable,
    StrictlyNameable,
)

# The prefix given to local constants, literals, etc to produce a name
# E.g. "hi" -> get_basename_fullname_pair(.) = "@Str"
# This must be a character that is not legal for standard Python _identifiers
# or else code elsewhere may break
LOCAL_VALUE_PREFIX = "@"


# RegEx patterns for blacklisted modules
MODULE_BLACKLIST_PATTERNS = {
    "(rattr|rattr\\..*)",
    "(package.rattr|packages.rattr\\..*)",
}

# Python builtins which are not functions, classes, etc.
PYTHON_LITERAL_BUILTINS = {"None", "True", "False", "Ellipsis"}

# Python builtins which end in "attr", these dynamically access attributes on a
# given object
# NOTE
#   These must be handled explicitly by `FunctionAnalyser` or anyother
#   `ast.NodeVisitor` implementation that records results/context and sees them
PYTHON_ATTR_BUILTINS = {"delattr", "getattr", "hasattr", "setattr"}

# All Python builtins that are present in the `RootContext`
PYTHON_BUILTINS = set(filter(lambda b: b not in PYTHON_LITERAL_BUILTINS, dir(builtins)))


def get_basename_fullname_pair(
    node: Nameable,
    safe: bool = False,
) -> Tuple[str, str]:
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

    """
    # Base case
    # ast.Name ⊂ StrictlyNameable
    if isinstance(node, ast.Name):
        return node.id, node.id

    # Recursive case
    # node ⊂ ( StrictlyNameable \ { ast.Name } )
    if isinstance(node, ast.Call):
        basename, sub_name = get_basename_fullname_pair(node.func, safe)
    elif isinstance(node, StrictlyNameable.__args__):
        basename, sub_name = get_basename_fullname_pair(node.value, safe)

    if isinstance(node, ast.Attribute):
        return basename, f"{sub_name}.{node.attr}"

    if isinstance(node, ast.Subscript):
        return basename, f"{sub_name}[]"

    if isinstance(node, ast.Call):
        if any(is_call_to(attr, node) for attr in PYTHON_ATTR_BUILTINS):
            return basename, ".".join(get_xattr_obj_name_pair(basename, node))

        return basename, f"{sub_name}()"

    if isinstance(node, ast.Starred):
        return basename, f"*{sub_name}"

    # Error case
    # node ⊂ Nameable ^ node ⊄ StrictlyNameable
    if safe:
        return (
            f"{LOCAL_VALUE_PREFIX}{node.__class__.__name__}",
            f"{LOCAL_VALUE_PREFIX}{node.__class__.__name__}",
        )

    _error_class: Type[TypeError] = TypeError
    if isinstance(node, ast.UnaryOp):
        _error_class = error.RattrUnaryOpInNameable
    elif isinstance(node, ast.BinOp):
        _error_class = error.RattrBinOpInNameable
    elif isinstance(node, Constant.__args__):
        _error_class = error.RattrConstantInNameable
    elif isinstance(node, Literal.__args__):
        _error_class = error.RattrLiteralInNameable
    elif isinstance(node, Comprehension.__args__):
        _error_class = error.RattrComprehensionInNameable
    else:
        _error_class = TypeError

    raise _error_class(f"line {node.lineno}: {ast.dump(node)}")


def get_basename(node: Nameable, safe: bool = False) -> str:
    """Return the `_identifier` of the innermost ast.Name node."""
    return get_basename_fullname_pair(node, safe)[0]


def get_fullname(node: Nameable, safe: bool = False) -> str:
    """Return the fullname of the given node."""
    return get_basename_fullname_pair(node, safe)[1]


def get_attrname(node: Nameable) -> str:
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


def unravel_names(node: Nameable) -> Iterable[str]:
    """Return the basename of each nameable in the given node.

    >>> ravelled_names = ast.parse("a, b = 1, 2").body[0].targets[0]
    >>> list(unravel_names(ravelled_names))
    ["a", "b"]

    >>> ravelled_names = ast.parse("(a, b), c, d.e = ...").body[0].targets[0]
    >>> list(unravel_names(ravelled_names))
    ["a", "b", "c", "d"]

    """
    if isinstance(node, StrictlyNameable.__args__):
        return [get_basename(node)]

    if isinstance(node, (ast.Tuple, ast.List)):
        ravelled = [unravel_names(i) for i in node.elts]
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

    return builtin in PYTHON_ATTR_BUILTINS


def get_xattr_obj_name_pair(
    xattr: str, node: ast.Call, warn: bool = False
) -> Tuple[str, str]:
    """Return the object-name pair for a call to getattr, setattr, etc."""
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
    # NOTE Call ∈ StrictlyNameable, thus base case comes second
    if isinstance(obj, StrictlyNameable.__args__):
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


def has_annotation(name: str, fn: AstDef) -> bool:
    """Return `True` if the function is decorated with the given annotation."""
    return name in map(get_attrname, fn.decorator_list)


def get_annotation(name: str, fn: AstDef) -> Optional[ast.expr]:
    """Return the decorator node for the given annotation on the function."""
    matching: List[ast.expr] = list()

    for decorator in fn.decorator_list:
        suffix = get_attrname(decorator)

        if suffix != name:
            continue

        matching.append(decorator)

    if len(matching) < 1:
        return None
    if len(matching) > 1:
        error.fatal(f"duplicated annotation '{name}' on '{fn.name}'", fn)

    return matching[0]


def safe_eval(expr: ast.expr, culprit: ast.AST) -> Optional[Any]:
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
    name: str, fn_def: FuncOrAsyncFunc
) -> Tuple[List[Any], Dict[str, Any]]:
    """Return the positional and keyword arguments of the annotation."""
    annotation = get_annotation(name, fn_def)

    pos_args: List[Any] = list()
    named_args: Dict[str, Any] = dict()

    if not annotation:
        return pos_args, named_args

    if not isinstance(annotation, ast.Call):
        return pos_args, named_args

    for arg in annotation.args:
        pos_args.append(safe_eval(arg, fn_def))

    for kwarg in annotation.keywords:
        named_args[kwarg.arg] = safe_eval(kwarg.value, fn_def)

    return pos_args, named_args


def is_name(name: Any) -> bool:
    """Return `True` if the given name is a valid Python `_identifier`.

    See: `parse_rattr_results_from_annotation(...)`
    """
    if not isinstance(name, str):
        return False

    if name.startswith("*"):
        name = name[1:]

    if name.startswith("@"):
        name = name[1:]

    return bool(re.match("^[A-Za-z_][A-Za-z\\d\\(\\)\\[\\]\\._]*$", name))


def is_set_of_names(set_of_names: Any) -> bool:
    """Return `True` if the given names are all valid Python `_identifier`s.

    See: `is_name(...`)
    See: `parse_rattr_results_from_annotation(...)`
    """
    if not isinstance(set_of_names, set):
        return False

    return all(is_name(name) for name in set_of_names)


def is_args(args: Any) -> bool:
    """Return `True` if the given names are all valid Python `_identifier`s.

    See: `is_name(...`)
    See: `parse_rattr_results_from_annotation(...)`
    """
    if not isinstance(args, tuple):
        return False

    if len(args) != 2:
        return False

    pos_args, named_args = args

    if not is_set_of_names(set(pos_args)):
        return False

    if not all(is_name(name) for name in named_args.keys()):
        return False
    if not all(is_name(arg) for arg in named_args.values()):
        return False

    return True


def parse_rattr_results_from_annotation(fn_def: AnyFunctionDef, context) -> FunctionIR:
    """Return the IR for the given function, assuming it is annotated."""
    # Check arguments
    expected = {"sets": set(), "gets": set(), "calls": list(), "dels": set()}
    pos_args, named_args = parse_annotation("rattr_results", fn_def)

    if pos_args != list():
        error.fatal(
            f"unexpected positional arguments to 'rattr_results'; expected "
            f"none, got {pos_args}",
            fn_def,
        )

    for name, default in expected.items():
        if name in named_args:
            continue
        named_args[name] = default

    if not all(key in expected.keys() for key in named_args.keys()):
        error.fatal(
            f"'rattr_results' expects one-or-many of the arguments "
            f"{set(expected.keys())}, found {set(named_args.keys())}",
            fn_def,
        )

    # Check argument types
    def __type_error(msg: str) -> None:
        error.fatal("type error:" + msg, fn_def)

    if not is_set_of_names(named_args.get("sets")):
        __type_error("'rattr_results' expects set of names for 'sets'")

    if not is_set_of_names(named_args.get("gets")):
        __type_error("'rattr_results' expects set of names for 'gets'")

    if not is_set_of_names(named_args.get("dels")):
        __type_error("'rattr_results' expects set of names for 'dels'")

    if not all(is_name(c[0]) for c in named_args.get("calls")):
        __type_error("'rattr_results' LHS of 'calls' to be names")

    if not all(is_args(c[1]) for c in named_args.get("calls")):
        __type_error("'rattr_results' expects args for 'calls'")

    if not all(len(c) == 2 for c in named_args.get("calls")):
        __type_error("'rattr_results' expects two elements per call")

    # Parse arguments as IR
    return {
        "sets": {parse_name(n) for n in named_args.get("sets")},
        "gets": {parse_name(n) for n in named_args.get("gets")},
        "dels": {parse_name(n) for n in named_args.get("dels")},
        "calls": {
            parse_call(n, a, context.get_call_target(n, fn_def))
            for n, a in named_args.get("calls")
        },
    }


def is_blacklisted_module(module: str) -> bool:
    """Return `True` if the given module matches a blacklisted pattern."""
    # Exclude stdlib modules such as the built-in "_thread"
    if is_stdlib_module(module):
        return False

    # Allow user specified exclusions via CLI
    blacklist = set.union(MODULE_BLACKLIST_PATTERNS, config.excluded_imports)

    return any(re.fullmatch(p, module) for p in blacklist)


def is_pip_module(module: str) -> bool:
    """Return `True` if the given module is pip installed."""
    pip_install_locations = (".+/site-packages.*",)

    try:
        spec = find_spec(module)
    except (AttributeError, ModuleNotFoundError, ValueError):
        spec = None

    if spec is None or spec.origin is None:
        return False

    # No backslashes, bad windows!
    spec.origin = spec.origin.replace("\\", "/")

    return any(re.fullmatch(p, spec.origin) for p in pip_install_locations)


def is_stdlib_module(module: str) -> bool:
    """Return `True` if the given module is in the Python standard library.

    >>> is_stdlib_module("math")
    True

    >>> is_stdlib_module("math.pi")
    True

    """
    return place_module(module) == "STDLIB"


def is_in_builtins(name_or_qualified_name: str) -> bool:
    return name_or_qualified_name in dir(builtins)


def get_function_def_args(
    fn_def: AnyFunctionDef,
) -> Tuple[List[str], Optional[str], Optional[str]]:
    """Return the arguments in the given function definition."""
    args = list()
    vararg = None
    kwarg = None

    for pos in fn_def.args.args:
        args.append(pos.arg)

    if fn_def.args.vararg:
        vararg = fn_def.args.vararg.arg

    if fn_def.args.kwarg:
        kwarg = fn_def.args.kwarg.arg

    return args, vararg, kwarg


def get_function_call_args(
    fn_call: ast.Call,
    self_name: Optional[str] = None,
) -> Tuple[List[str], Dict[str, str]]:
    """Return the arguments in the given function call.

    Method/initialiser calls can provide a `self_name` to prepend to the
    positional arguments.

    """
    _unsupported = "{} not supported in function calls"

    args = list()
    kwargs = dict()

    for arg in fn_call.args:
        if isinstance(arg, ast.Starred):
            error.error(_unsupported.format("iterable unpacking"), fn_call)

        args.append(get_fullname(arg, safe=True))

    for kwarg in fn_call.keywords:
        expected, got = kwarg.arg, kwarg.value

        if expected is None:
            error.fatal(_unsupported.format("dictionary unpacking"), fn_call)
            return list(), dict()  # Make mypy happy

        kwargs[expected] = get_fullname(got, safe=True)

    if self_name is not None:
        args = [self_name, *args]

    return args, kwargs


def remove_call_brackets(call: str):
    """Return the given string with the trailing `()` removed, if present.

    NOTE Made redundant by `str.removesuffix("()")` in Python 3.9+
    """
    if call.endswith("()"):
        return call[:-2]

    return call


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

    def __init__(self, file: str) -> None:
        self.lines = 0
        self.contents = ""
        self.file = file

    def __enter__(self):
        with open(self.file, "r") as f:
            for _lineno, line in enumerate(f):
                self.contents += line
            self.lines = _lineno + 1
        return self.lines, self.contents

    def __exit__(self, *_):
        pass


def get_starred_imports(
    symbols: List[Symbol],
    seen: Iterable[Import],
) -> List[Import]:
    """Return the starred imports in the given symbols."""
    starred: List[Import] = list()

    for symbol in symbols:
        if not isinstance(symbol, Import):
            continue

        if symbol.name != "*":
            continue

        if symbol in seen:
            continue

        starred.append(symbol)

    return starred


@contextmanager
def enter_file(new_file: str) -> Generator:
    """Set `config.current_file` for the scope of a context."""
    old_file = config.current_file
    config.current_file = new_file
    yield
    config.current_file = old_file


def get_function_body(node: AnyFunctionDef) -> List[ast.stmt]:
    """Return the body of the given function as a list of statements."""
    if isinstance(node, ast.Lambda):
        return [node.body]

    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.body

    raise TypeError(f"line {node.lineno}: {ast.dump(node)}")


def get_assignment_targets(node: AnyAssign) -> List[ast.expr]:
    """Return the given assignment's targets as a list."""
    if isinstance(node, ast.Assign):
        return node.targets

    if isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        return [node.target]

    raise TypeError(f"line {node.lineno}: {ast.dump(node)}")


def assignment_is_one_to_one(node: AnyAssign) -> bool:
    """Return `True` if the given assignment is one-to-one."""
    _iterable = (ast.Tuple, ast.List)

    targets = get_assignment_targets(node)

    # Ensure LHS is singular
    if len(targets) > 1 or any(isinstance(t, _iterable) for t in targets):
        return False

    return not isinstance(node.value, _iterable)


def lambda_in_rhs(node: AnyAssign) -> bool:
    """Return `True` if the RHS of the given assignment contains a lambda."""
    _iterable = (ast.Tuple, ast.List)

    if isinstance(node.value, ast.Lambda):
        return True
    elif isinstance(node.value, _iterable):
        return any(isinstance(v, ast.Lambda) for v in node.value.elts)
    else:
        return False


def class_in_rhs(node: AnyAssign, context: Any) -> bool:
    """Return `True` if the RHS of the given assignment is a class init."""
    _iterable = (ast.Tuple, ast.List)

    def expr_is_class(expr):
        full = get_fullname(expr, safe=True)

        try:
            target = context.get_call_target(full, expr, False)
        except ValueError:
            return False

        return isinstance(target, Class)

    if isinstance(node.value, ast.Call):
        return expr_is_class(node.value)
    elif isinstance(node.value, _iterable):
        return any(expr_is_class(e) for e in node.value.elts)
    else:
        return False


def is_starred_import(node: Union[ast.Import, ast.ImportFrom]) -> bool:
    """Return `True` if the given import is a `from module import *`."""
    if not isinstance(node, ast.ImportFrom):
        return False

    return any(target.name == "*" for target in node.names)


def is_relative_import(node: Union[ast.Import, ast.ImportFrom]) -> bool:
    """Return `True` if the given import is a relative import."""
    if not isinstance(node, ast.ImportFrom):
        return False

    return node.level != 0


def module_name_from_file_path(file: str) -> Optional[str]:
    """Return the recognised name of the given module."""
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
        try:
            spec = find_spec(p)
            if spec is not None:
                break
        except (AttributeError, ModuleNotFoundError, ValueError):
            continue

    return p


def get_absolute_module_name(base: str, level: int, target: str) -> str:
    """Return the absolute import for the given relative import."""
    level -= int(config.current_file.endswith("__init__.py"))

    if level > 0:
        new_base = ".".join(base.split(".")[:-level])
    else:
        new_base = base

    return f"{new_base}.{target}"


def get_function_form(node: AnyFunctionDef) -> str:
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


def re_filter_ir(d: Dict[Symbol, Any], filter_by: str) -> Dict[str, Any]:
    """Return the given dict filtered by the given regular expression."""
    if not filter_by:
        return d

    return {f: d[f] for f in filter(lambda f: re.fullmatch(filter_by, f.name), d)}


def re_filter_results(d: Dict[str, Any], filter_by: str) -> Dict[str, Any]:
    """Return the given dict filtered by the given regular expression."""
    if not filter_by:
        return d

    return {f: d[f] for f in filter(lambda f: re.fullmatch(filter_by, f), d)}


def is_excluded_name(name: str) -> bool:
    """Return `True` if the given name is in the exclude list."""
    return any(re.fullmatch(x, name) for x in config.excluded_names)


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

    >>> call = ast.parse("get_sub_attr(get_sub_attr(o, 'in'), 'out')").body[0].value # noqa
    >>> get_dynamic_name("get_sub_attr", call, "{first}.mid.{second}")
    Name("o.in.mid.out", "o")

    >>> call = ast.parse("get_sub(obj)").body[0].value
    >>> get_dynamic_name("get_sub", call, "{first}.sub")
    Name("obj.sub", "obj")

    """
    first, second = get_xattr_obj_name_pair(fn_name, node, warn=True)

    basename = first.split(".")[0].replace("*", "").replace("[]", "").replace("()", "")

    return Name(pattern.format(first=first, second=second), basename)


def get_file_hash(filepath: str, blocksize: int = 2**20) -> str:
    """Return the hash of the given file, with a default blocksize of 1MiB."""
    _hash = hashlib.md5()

    if not isfile(filepath):
        return _hash

    with open(filepath, "rb") as f:
        while True:
            buffer = f.read(blocksize)

            if not buffer:
                break

            _hash.update(buffer)

    return _hash.hexdigest()


def cache_is_valid(filepath: str, cache_filepath: str) -> bool:
    """Return `True` if the cache has the correct hash."""
    if not isfile(filepath):
        return False

    if isfile(cache_filepath):
        with open(cache_filepath, "r") as f:
            cache: Dict[str, Any] = json.load(f)
    else:
        return False

    received_hash = cache.get("filehash", None)
    expected_hash = get_file_hash(filepath)

    if filepath != cache.get("filepath", None):
        return False

    if received_hash != expected_hash:
        return False

    # Check imports
    for _import in cache.get("imports", dict()):
        file, hash = _import["filepath"], _import["filehash"]
        if hash != get_file_hash(file):
            return False

    return True


def create_cache(
    results: FileResults, imports: Set[str], encoder: json.JSONEncoder
) -> None:
    """Create a the cache and write it to the cache file.

    NOTE:
        The attribute `imports` should hold the file name of every directly and
        indirectly imported source code file.

    Cache file format (JSON):
    {
        "filepath": ...,    # the file the results belong to
        "filehash": ...,    # the MD5 hash of the file when it was cached

        "imports": [
            {"filename": ..., "filehash": ...,},
        ]

        "results":
            # For each function in the file:
            "function_name": {
                "sets"  : ["obj.attr", ...],
                "gets"  : ["obj.attr", ...],
                "dels"  : ["obj.attr", ...],
                "calls" : ["obj.attr", ...],
            },
            ...
        }
    }

    """
    to_cache = dict()

    to_cache["filepath"] = config.file
    to_cache["filehash"] = get_file_hash(config.file)
    to_cache["imports"] = [
        {"filepath": file, "filehash": get_file_hash(file)} for file in imports
    ]
    to_cache["results"] = deepcopy(results)

    with open(config.cache, "w") as f:
        json.dump(to_cache, f, cls=encoder, indent=4)
