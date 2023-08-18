from __future__ import annotations

from functools import lru_cache
from importlib.util import find_spec
from itertools import accumulate
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.machinery import ModuleSpec


def with_call_brackets(call: str) -> str:
    """Return the given string with call brackets added if absent.

    >>> without_call_brackets("keep_my_call_brackets()")
    "keep_my_call_brackets()"
    >>> without_call_brackets("i_dont_have_call_brackets")
    "i_dont_have_call_brackets()"
    """
    if not call.endswith("()"):
        return f"{call}()"

    return call


def without_call_brackets(call: str) -> str:
    """Return the given string with call brackets removed if present.

    >>> without_call_brackets("remove_my_call_brackets()")
    "remove_my_call_brackets"
    >>> without_call_brackets("i_dont_have_call_brackets")
    "i_dont_have_call_brackets"

    #### NOTE
    Made redundant by `str.removesuffix("()")` in Python 3.9+
    """
    if not call.endswith("()"):
        return call

    return call[:-2]


def get_basename_from_name(name: str) -> str:
    """Return the basename for the given name.

    >>> get_basename_from_name("my_var")
    "my_var"

    >>> get_basename_from_name("my_var.attr")
    "my_var"

    >>> get_basename_from_name("*my_var.attr.method()")
    "my_var"
    """
    return without_call_brackets(name).replace("*", "").split(".", maxsplit=1)[0]


def get_possible_module_names(name: str) -> list[str]:
    """Return the possible module names for the given name, in relevance order.

    >>> get_possible_module_names("a.b.c.d")
    ["a.b.c.d", "a.b.c", "a.b", "a"]

    >>> get_possible_module_names("os.path.join")
    ["os.path.join", "os.path", "os"]

    >>> get_possible_module_names("math")
    ["math"]
    """

    def _is_well_formed(m: str) -> bool:
        return not m.endswith(".")

    def _dotted(parts: list[str], *, sep: str = ".") -> list[str]:
        for part in parts:
            yield part
            yield sep

    parts = name.split(".")
    valid_module_names = [m for m in accumulate(_dotted(parts)) if _is_well_formed(m)]

    return [m for m in reversed(valid_module_names)]


@lru_cache(maxsize=None)
def get_module_name_and_spec(name: str) -> tuple[str, ModuleSpec] | tuple[None, None]:
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
    module_spec_pairs: list[tuple[str, ModuleSpec]] = []

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
