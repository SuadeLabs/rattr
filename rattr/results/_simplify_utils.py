from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING, TypedDict

from rattr import error
from rattr.config import Config
from rattr.models.symbol import Name

if TYPE_CHECKING:
    from typing import Final, Literal

    from rattr.ast.types import Identifier
    from rattr.models.ir import FunctionIr
    from rattr.models.symbol import Call, Func


VARARG_NAME: Final = f"{Config.LITERAL_VALUE_PREFIX}{ast.Tuple.__name__}"
KWARGS_NAME: Final = f"{Config.LITERAL_VALUE_PREFIX}{ast.Dict.__name__}"


def construct_call_swaps(func: Func, call: Call) -> dict[Identifier, Identifier]:
    """Return the map of local function names to bound names."""
    # TODO
    # The func.interface needs to store the default arguments, the ast makes this tricky
    # as it is just a list of default values (not a dict of argument to default value)
    # but as you can't have a non-defaulted value after a defaulted one we can work this
    # out at when we build the context.
    # TODO
    # Handle vararg and kwargs
    swaps: dict[Identifier, Identifier] = {}

    # Copy the input args / interface so we can pop to keep track of state
    interface = func.interface.as_consumable_call_interface()
    call_args = [a for a in call.args.args]
    call_kwargs = {k: v for k, v in call.args.kwargs.items()}

    while True:
        if not interface.posonlyargs:
            break

        if not call_args:
            error.error(
                f"call to {func.name!r} expected {len(func.interface.posonlyargs)} "
                f"posonlyargs but only received {len(call.args.args)} positional "
                f"arguments",
                culprit=call,
            )
            return {}

        target = interface.posonlyargs.pop(0)
        replacement = call_args.pop(0)

        swaps[target] = replacement

    while True:
        if not interface.args:
            break  # no error as the remaining args may be supplied by kw

        if not call_args:
            break

        target = interface.args.pop(0)
        replacement = call_args.pop(0)

        swaps[target] = replacement

    if interface.vararg is not None:
        swaps[interface.vararg] = VARARG_NAME
        call_args = []

    # We can't be very specific here as we don't know if any of the positional arguments
    # have defaults (yet, we need a better CallInterface, see the todo above).
    if call_args:
        error.error(
            f"call to {func.name!r} received too many positional arguments",
            culprit=call,
        )

    # interface.args may be [] or [...]
    # call_args is []

    unexpected_keyword_arguments: list[Identifier] = []
    arguments_given_by_position_and_name: list[Identifier] = []

    for target, replacement in call_kwargs.items():
        if target in swaps:
            arguments_given_by_position_and_name.append(target)

        if target in interface.args:
            interface.args.remove(target)
            swaps[target] = replacement
        elif target in interface.kwonlyargs:
            interface.kwonlyargs.remove(target)
            swaps[target] = replacement
        elif interface.kwarg is not None:
            swaps[interface.kwarg] = KWARGS_NAME
        elif target not in func.interface.all:
            unexpected_keyword_arguments.append(target)

    if unexpected_keyword_arguments:
        error.error(
            f"call to {func.name!r} received unexpected keyword arguments: "
            f"{unexpected_keyword_arguments}",
            culprit=call,
        )

    if arguments_given_by_position_and_name:
        error.error(
            f"call to {func.name!r} received the arguments "
            f"{arguments_given_by_position_and_name} by position and name",
            culprit=call,
        )

    # There could be interface.args remaining but for now we don't know if they might
    # be defaulted so we can't do anything here
    # There could also be interface.kwonlyargs but, likewise, they could have defaults

    return swaps


def unbind_ir_with_call_swaps(
    ir: FunctionIr,
    swaps: dict[Identifier, Identifier],
) -> FunctionIr:
    return {
        "gets": {unbind_name(n, swaps.get(n.basename, n.basename)) for n in ir["gets"]},
        "sets": {unbind_name(n, swaps.get(n.basename, n.basename)) for n in ir["sets"]},
        "dels": {unbind_name(n, swaps.get(n.basename, n.basename)) for n in ir["dels"]},
        "calls": ir["calls"],
    }


def unbind_name(symbol: Name, new_basename: Identifier) -> Name:
    """Return a new symbol bound to the new base name."""
    if symbol.basename == new_basename:
        return symbol

    if symbol.name.startswith("*"):
        old, new = f"*{symbol.basename}", f"*{new_basename}"
    else:
        old, new = symbol.basename, new_basename

    if not symbol.name.startswith(old):
        # If this is ever true then we'd need to do a regex over:
        # r"^(?P<star>\*)?(?P<basename>\w+)(?P<remainder>(\.\w+)*)(?P<subscript>\[\])?$"
        # constructing a new string from the match groups with basename replaced with
        # the new_basename if it matches the old basename or else returning the target.
        # However, this is much faster (0.25s for 1M vs 0.71s for 1M) and the assumption
        # holds.
        raise ValueError("never")

    new_name = symbol.name.replace(old, new, 1)
    return Name(name=new_name, basename=new_basename, location=symbol.location)


re_name = re.compile(
    r"^(?P<star>\*)?"
    r"(?P<basename>\w+)"
    r"(?P<remainder>(\.\w+)*)"
    r"(?P<subscript>\[\])?$"
)


class ReNameMatches(TypedDict):
    star: Literal["*"] | None
    basename: str
    remainder: str
    subscript: Literal["[]"] | None


def fast_re_replace(target: Identifier, old: Identifier, new: Identifier) -> Identifier:
    matches: ReNameMatches = re_name.fullmatch(target)

    if matches is None:
        return target
    if matches["basename"] != old:
        return target

    star = matches["star"] or ""
    subscript = matches["subscript"] or ""

    return f"{star}{new}{matches['remainder']}{subscript}"
