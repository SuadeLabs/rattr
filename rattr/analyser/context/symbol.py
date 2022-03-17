"""Symbols for use in context and intermediate results.

Symbol hash and equivalence only holds when the symbols are within the same
context.

Symbol `name` is the Python `_identifier` for the given symbol.

"""

from dataclasses import dataclass
from importlib.machinery import ModuleSpec
from importlib.util import find_spec
from itertools import accumulate, chain, filterfalse
from typing import Dict, List, Optional, Tuple, Union

from rattr import config


@dataclass
class Symbol:
    name: str

    def _is(self, symbol_type) -> bool:
        return isinstance(self, symbol_type)

    def __hash__(self) -> int:
        return hash(repr(self))


@dataclass
class Name(Symbol):
    basename: Optional[str] = None

    def __post_init__(self) -> None:
        if self.basename is None:
            self.basename = self.name

    def __hash__(self) -> int:
        return hash(repr(self))


@dataclass
class Builtin(Symbol):
    has_affect: bool

    def __hash__(self) -> int:
        return hash(repr(self))


@dataclass
class Import(Symbol):
    qualified_name: Optional[str] = None
    module_name: Optional[str] = None
    module_spec: Optional[ModuleSpec] = None

    def __post_init__(self) -> None:
        if self.qualified_name is None:
            self.qualified_name = self.name

        self.module_name, self.module_spec = get_module_name_and_spec(
            self.qualified_name
        )

    def __hash__(self) -> int:
        return hash(repr(self))


@dataclass
class Func(Symbol):
    args: List[str]
    vararg: Optional[str]
    kwarg: Optional[str]
    is_async: bool = False
    defined_in: Optional[str] = None

    def __post_init__(self) -> None:
        self.defined_in = config.current_file

    def __hash__(self) -> int:
        return hash(repr(self))


@dataclass
class Class(Symbol):
    """Represent the class itself and the target of `<class>.__call__()`.

    NOTE
        If no initialiser is found; args, vararg, and kwarg will all be None
        If an initialiser is found; args will be an initialised list (could be
        empty), but vararg and kwarg may-or-may-not be None

    """

    args: Optional[List[str]]
    vararg: Optional[str]
    kwarg: Optional[str]
    defined_in: Optional[str] = None

    def __post_init__(self) -> None:
        self.defined_in = config.current_file

    def __hash__(self) -> int:
        return hash(repr(self))


CallTarget = Union[
    Func,
    Class,
    Builtin,
    Import,
]


@dataclass
class Call(Symbol):
    args: List[str]
    kwargs: Dict[str, str]
    target: Optional[Symbol] = None

    def __hash__(self) -> int:
        return hash(repr(self))


def parse_name(name: str) -> Name:
    return Name(name, name.replace("*", "").split(".")[0])


def parse_call(
    callee: str,
    args: Tuple[List[str], Dict[str, str]],
    target: Optional[CallTarget] = None,
) -> Call:
    if not callee.endswith("()"):
        callee += "()"

    return Call(callee, *args, target)


def get_possible_module_names(name: str) -> List[str]:
    """Return the possible modules for the given name, in relevance order.

    >>> get_possible_module_names("a.b.c.d")
    ["a.b.c.d", "a.b.c", "a.b", "a"]

    >>> get_possible_module_names("os.path.join")
    ["os.path.join", "os.path", "os"]

    Inline comments show the `get_possible_module_names("a.b.c.d")` as a worked
    example.

    """
    # IN: "a.b.c.d"
    # "a", "b", "c", "d"
    parts = name.split(".")

    # ("a", "."), ("b", "."), ("c", "."), ("d", ".")
    dotted_parts = chain.from_iterable(zip(parts, ["."] * len(parts)))

    # "a", "a.", "a.b", "a.b.", "a.b.c", ...
    possible = accumulate(dotted_parts)

    # "a", "a.b", "a.b.c", "a.b.c.d"
    well_formed = filterfalse(lambda p: p.endswith("."), possible)

    # "a.b.c.d", "a.b.c", "a.b", "a"
    ordered = reversed(list(well_formed))

    return list(ordered)


def get_module_name_and_spec(
    name: str,
) -> Union[Tuple[str, ModuleSpec], Tuple[None, None]]:
    """Return the `ModuleSpec` for an imported name.

    If `name` is a module (e.g. `math`) then the spec of the module will be
    returned.

    >>> get_module_name_and_spec("math")
    "math", ModuleSpec(name='math', loader=... origin='built-in')

    If `name` is the fully qualified name of a name within a module then the
    spec of the containing module will be given (e.g. spec of "math" for
    the name "math.pi").

    >>> get_module_name_and_spec("os.path.join")
    "os.path", ModuleSpec(name='posixpath', loader=..., origin=...)

    """
    module_spec_pairs: List[Tuple[str, ModuleSpec]] = list()

    # Filter for valid modles, in acceptance order
    for module in get_possible_module_names(name):
        if module.endswith("."):
            continue

        try:
            spec = find_spec(module)
        except (AttributeError, ModuleNotFoundError, ValueError):
            spec = None

        if spec is None:
            continue

        module_spec_pairs.append((module, spec))

    if len(module_spec_pairs) == 0:
        return None, None

    return module_spec_pairs[0]
