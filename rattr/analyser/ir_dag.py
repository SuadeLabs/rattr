"""Represent the IR of functions as a DAG, for simplification."""
from __future__ import annotations

import ast
import copy
from typing import TYPE_CHECKING

import attrs
from attrs import field

from rattr import error
from rattr.analyser.types import FunctionIr, ImportIrs
from rattr.analyser.util import (
    is_blacklisted_module,
    is_excluded_name,
    is_pip_module,
    is_stdlib_module,
)
from rattr.config import Config
from rattr.models.ir import FileIr
from rattr.models.symbol import Builtin, Call, Class, Func, Import, Name
from rattr.module_locator.util import derive_module_name_from_path

if TYPE_CHECKING:
    from rattr.ast.types import Identifier


@attrs.mutable
class IrDagNode:
    """Represent a function call for simplification."""

    # TODO
    # Refactor populate and simplify to be functions, not methods, and non-recursive via
    # a deque.

    call: Call
    func: Func
    func_ir: FunctionIr
    file_ir: FileIr
    import_irs: ImportIrs

    children: list[IrDagNode] = field(factory=list)

    def populate(self, seen: set[Call] | None = None) -> set[Call]:
        """Populate this node, and it's children, recursively.

        In principle, BFS the calls to construct the DAG. Calls may have cycles
        (i.e. direct or indirect recursion), however these can be ignored if
        the same function is called with the same arguments -- thus eliminating
        cycles; producing a DAG.
        """
        if seen is None:
            seen = set()

        # Find children
        for call in self.func_ir["calls"]:
            if call in seen:
                continue

            target, target_ir = find_call_target(
                call,
                self.file_ir,
                self.import_irs,
                caller=self.func,
            )

            if target is None or target_ir is None:
                continue

            self.children.append(
                IrDagNode(
                    call,
                    target,
                    target_ir,
                    self.file_ir,
                    self.import_irs,
                )
            )

            seen.add(call)

        # Populate children
        for child in self.children:
            seen = child.populate(seen)

        return seen

    def simplify(self) -> FunctionIr:
        """Return the IR modified to include dependent calls.

        NOTE
        Assumes that the root IrDagNode has been populated via `populate`!
        """
        # Leafs are already simplified
        if len(self.children) == 0:
            return copy.deepcopy(self.func_ir)

        # Simplified non-terminal nodes are the combination of themselves and their
        # children partially unbound
        child_irs = [(child.simplify(), child) for child in self.children]

        simplified: FunctionIr = copy.deepcopy(self.func_ir)

        for child_ir, child in child_irs:
            swaps = construct_swap(child.func, child.call)
            unbound_child = partially_unbind(child_ir, swaps)

            simplified["sets"] |= unbound_child["sets"]
            simplified["gets"] |= unbound_child["gets"]
            simplified["dels"] |= unbound_child["dels"]

        return simplified


def find_call_target(
    call: Call,
    file_ir: FileIr,
    import_irs: ImportIrs,
    *,
    caller: Func | None = None,
) -> tuple[None, None] | tuple[Func, FunctionIr]:
    """Return the func and IR of the called function."""
    # TODO Should this trigger a warning?
    if call.target is None:
        return None, None

    if isinstance(call.target, Builtin):
        return None, None

    if isinstance(call.target, Func):
        return resolve_function(call, file_ir, import_irs, caller=caller)

    # NOTE Procedural parameter, etc, can't be resolved
    if isinstance(call.target, Name):
        return None, None

    if isinstance(call.target, Class):
        return resolve_class_init(call, file_ir, import_irs)

    if isinstance(call.target, Import):
        return resolve_import(call.target, import_irs)

    raise TypeError("'callee' must be a CalleeTarget")


def resolve_function(
    call: Call,
    file_ir: FileIr,
    import_irs: ImportIrs,
    *,
    caller: Func | None = None,
) -> tuple[None, None] | tuple[Func, FunctionIr]:
    if call.target is None:
        raise ImportError

    error_ = f"unable to resolve call to {call.target.name!r}"

    if caller is not None:
        error_ = f"{error_} in {caller.name!r}"

    try:
        func, ir = __resolve_target_and_ir(call, file_ir, import_irs)
    except ImportError:
        if is_excluded_name(call.target.name):
            error.error(f"{error_}, the call target matches an exclusion", culprit=call)
        elif "." not in call.name:
            error.error(f"{error_}, likely a nested function or ignored", culprit=call)
        else:
            error.info(f"{error_}'", culprit=call)
        return None, None

    return func, ir


def resolve_class_init(
    call: Call,
    file_ir: FileIr,
    import_irs: ImportIrs,
) -> tuple[None, None] | tuple[Func, FunctionIr]:
    error_ = f"unable to resolve initialiser for {call.name!r}"

    try:
        cls, ir = __resolve_target_and_ir(call, file_ir, import_irs)
    except ImportError:
        error.error(error_, culprit=call)
        return None, None

    return cls, ir


def resolve_import(
    target: Import,
    import_irs: ImportIrs,
) -> tuple[None, None] | tuple[Func, FunctionIr]:
    """Return the `Func` and IR for the given import."""
    config = Config()
    arguments = config.arguments

    if target.module_name is None:
        raise ImportError

    module_ir = import_irs.get(target.module_name, None)

    if is_blacklisted_module(target.module_name):
        return None, None

    if not arguments.follow_local_imports:
        error.info(
            f"ignoring call to imported function {target.name!r}",
            culprit=target,
        )
        return None, None

    if not arguments.follow_pip_imports and is_pip_module(target.module_name):
        error.info(
            f"ignoring call to function {target.name!r} imported from pip installed "
            f"module {target.module_name!r}",
            culprit=target,
        )
        return None, None

    if not arguments.follow_stdlib_imports and is_stdlib_module(target.module_name):
        error.info(
            f"ignoring call to function {target.name!r} imported from stdlib module "
            f"{target.module_name!r}",
            culprit=target,
        )
        return None, None

    if target.module_name is None:
        raise ValueError(f"Target {target.name!r} has no module name")

    if module_ir is None:
        raise ImportError(f"Import {target.module_name!r} not found")

    local_name = target.name.replace(f"{target.module_name}.", "").removesuffix("()")
    new_target = module_ir.context.get(local_name)

    if isinstance(new_target, (Func, Class)):
        ir = module_ir.get(new_target)

        # NOTE If the imported function is ignored then it will have no IR
        if ir is None:
            error.error(
                f"unable to resolve imported callable {local_name!r} in "
                f"{target.module_name!r}, it is likely ignored",
                culprit=target,
            )
            return None, None

        return new_target, ir

    if isinstance(new_target, Import):
        return resolve_import(new_target, import_irs)

    # NOTE
    # When reaching here the target may be a call to a method on an imported instance

    if new_target is None and "." in local_name:
        error.info(
            f"unable to resolve call to method {local_name!r} in import "
            f"{target.module_name!r}",
            culprit=target,
        )
        return None, None

    error.error(
        f"unable to resolve call to {local_name!r} in import {target.module_name!r}",
        culprit=target,
    )
    return None, None


def partially_unbind_name(symbol: Name, new_basename: str) -> Name:
    """Return a new symbol bound to the new base name."""

    def as_name(name: Identifier, basename: Identifier | None = None) -> Name:
        return Name(name, basename, location=symbol.location)

    if symbol.basename == new_basename:
        return as_name(symbol.name, symbol.basename)

    new_name = symbol.name
    if symbol.name.startswith("*"):
        new_name = symbol.name.replace(f"*{symbol.basename}", f"*{new_basename}", 1)
    else:
        new_name = symbol.name.replace(symbol.basename, new_basename, 1)

    return as_name(new_name, new_basename)


def partially_unbind(func_ir: FunctionIr, swaps: dict[str, str]) -> FunctionIr:
    """Return the partially unbound results for the given function."""
    return {
        "sets": {
            partially_unbind_name(name, swaps.get(name.basename, name.basename))
            for name in func_ir["sets"]
        },
        "gets": {
            partially_unbind_name(name, swaps.get(name.basename, name.basename))
            for name in func_ir["gets"]
        },
        "dels": {
            partially_unbind_name(name, swaps.get(name.basename, name.basename))
            for name in func_ir["dels"]
        },
        "calls": func_ir["calls"],
    }


def construct_swap(func: Func, call: Call) -> dict[Identifier, Identifier]:
    """Return the map of local function names to bound names."""
    # TODO
    # The func.interface needs to store the default arguments, the ast makes this tricky
    # as it is just a list of default values (not a dict of argument to default value)
    # but as you can't have a non-defaulted value after a defaulted one we can work this
    # out at when we build the context.
    # TODO
    # Handle vararg and kwargs
    config = Config()

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
        swaps[interface.vararg] = f"{config.LITERAL_VALUE_PREFIX}{ast.Tuple.__name__}"
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

    while True:
        if not call_kwargs:
            break

        (target, replacement) = call_kwargs.popitem()

        if target in swaps:
            arguments_given_by_position_and_name.append(target)

        if target in interface.args:
            interface.args.remove(target)
            swaps[target] = replacement
        elif target in interface.kwonlyargs:
            interface.kwonlyargs.remove(target)
            swaps[target] = replacement
        elif interface.kwarg is not None:
            swaps[interface.kwarg] = f"{config.LITERAL_VALUE_PREFIX}{ast.Dict.__name__}"
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


def __resolve_target_and_ir(
    callee: Call,
    file_ir: FileIr,
    import_irs: ImportIrs,
) -> tuple[Func, FunctionIr]:
    """Helper function for `resolve_function` and `resolve_class`."""
    # HACK
    # If a class is called before it's initialiser is visited then callee.target is a
    # placeholder without the correct interface so we must discard the callee.target and
    # use the symbol from the module_ir
    if isinstance(callee.target, Class):
        target = __resolve_real_class_target(callee.target, file_ir, import_irs)
    else:
        target = callee.target

    if target in file_ir:
        assert target is not None, "unable to resolve callee target"
        return target, file_ir[target]

    if target is None:
        raise ImportError

    filename = target.location.defined_in
    module = derive_module_name_from_path(filename)

    if module is None:
        raise ModuleNotFoundError(f"unable to find module for {str(filename)!r}")

    module_ir = import_irs.get(module)

    if module_ir is None:
        raise ImportError

    if target not in module_ir:
        raise ImportError

    return target, module_ir[target]


def __resolve_real_class_target(
    target: Class,
    file_ir: FileIr,
    import_irs: ImportIrs,
) -> Class:
    for symbol in file_ir:
        if isinstance(symbol, Class) and target.name == symbol.name:
            return symbol

    for _, import_ir in import_irs.items():
        for symbol in import_ir:
            if isinstance(symbol, Class) and target.name == symbol.name:
                return symbol

    return target
