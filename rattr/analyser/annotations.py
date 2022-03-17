"""Annotations to be imported for use by Rattr analysed code."""

from typing import Dict, List, Optional, Set, Tuple

# A set of names, e.g.: "@BinOp", "x.attr", "var_one"
Names = Set[str]

# LHS: positional args, RHS: named args
CalleeArgs = Tuple[List[str], Dict[str, str]]

# LHS: callee name, RHS: callee args
Calls = List[Tuple[str, CalleeArgs]]


def rattr_ignore():
    """Do not parse the decorated function, thus omitted from the results."""

    def _inner(f, *args, **kwargs):
        return f

    return _inner


def rattr_results(
    gets: Optional[Names] = None,
    sets: Optional[Names] = None,
    dels: Optional[Names] = None,
    calls: Optional[Calls] = None,
):
    """Explicitly provide results for a function which will then be ignored."""

    def _inner(f, *args, **kwargs):
        return f

    return _inner
