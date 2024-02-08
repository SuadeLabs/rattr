"""Represent the IR of functions as a DAG, for simplification."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rattr import error
from rattr.analyser.types import FunctionIr, ImportsIr
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


def __prefix(func: Func | None) -> str:
    """HACK We no longer have `culprit` so manually construct prefix."""
    config = Config()

    if func is None:
        return ""

    file_location = func.location.defined_in
    formatted_file_location = config.get_formatted_path(file_location)

    if formatted_file_location is None:
        return ""

    return "\033[1m{}:\033[0m".format(formatted_file_location)


def __resolve_target_and_ir(
    callee: Call,
    file_ir: FileIr,
    imports_ir: ImportsIr,
) -> tuple[Func, FunctionIr]:
    """Helper function for `resolve_function` and `resolve_class`."""
    if callee.target in file_ir:
        assert callee.target is not None, "unable to resolve callee target"
        return callee.target, file_ir[callee.target]

    if callee.target is None:
        raise ImportError

    filename = callee.target.location.defined_in
    module = derive_module_name_from_path(filename)

    if module is None:
        raise ModuleNotFoundError(f"unable to find module for {str(filename)!r}")

    module_ir = imports_ir.get(module)

    if module_ir is None:
        raise ImportError

    if callee.target not in module_ir:
        raise ImportError

    return callee.target, module_ir[callee.target]


def resolve_function(
    callee: Call,
    file_ir: FileIr,
    imports_ir: ImportsIr,
    caller: Func | None = None,
) -> tuple[None, None] | tuple[Func, FunctionIr]:
    if callee.target is None:
        raise ImportError

    _msg = f"{__prefix(caller)} unable to resolve call to {callee.target.name!r}"

    if caller is not None:
        _msg = f"{_msg} in {caller.name!r}"

    try:
        func, ir = __resolve_target_and_ir(callee, file_ir, imports_ir)
    except ImportError:
        if is_excluded_name(callee.target.name):
            error.error(f"{_msg}, the call target matches an exclusion")
        elif "." not in callee.name:
            error.error(f"{_msg}, likely a nested function or ignored")
        else:
            error.info(f"{_msg}'")
        return None, None

    return func, ir


def resolve_class_init(
    callee: Call,
    file_ir: FileIr,
    imports_ir: ImportsIr,
    caller: Func | None = None,
) -> tuple[None, None] | tuple[Func, FunctionIr]:
    _where = __prefix(caller)

    try:
        cls, ir = __resolve_target_and_ir(callee, file_ir, imports_ir)
    except ImportError:
        error.error(f"{_where} unable to resolve initialiser for {callee.name!r}")
        return None, None

    return cls, ir


def resolve_import(
    name: Identifier,
    target: Import,
    imports_ir: ImportsIr,
    caller: Func | None = None,
) -> tuple[None, None] | tuple[Func, FunctionIr]:
    """Return the `Func` and IR for the given import."""
    _where = __prefix(caller)
    config = Config()

    if target.module_name is None:
        raise ImportError

    module_ir = imports_ir.get(target.module_name, None)

    _follow_imports = config.arguments.follow_imports
    _follow_pip_imports = config.arguments.follow_pip_imports
    _follow_stdlib_imports = config.arguments.follow_stdlib_imports

    if is_blacklisted_module(target.module_name):
        return None, None

    if not _follow_imports:
        error.info(f"{_where} ignoring call to imported function {target.name!r}")
        return None, None

    if not _follow_pip_imports and is_pip_module(target.module_name):
        error.info(
            f"{_where} ignoring call to function {target.name!r} imported from pip "
            f"installed module {target.module_name!r}"
        )
        return None, None

    if not _follow_stdlib_imports and is_stdlib_module(target.module_name):
        error.info(
            f"{_where} ignoring call to function {target.name!r} imported from stdlib "
            f"module {target.module_name!r}"
        )
        return None, None

    if target.module_name is None:
        raise ValueError(f"Target {target.name!r} has no module name")

    if module_ir is None:
        raise ImportError(f"Import {target.module_name!r} not found")

    local_name = (
        name.replace(target.name, target.qualified_name)
        .replace(f"{target.module_name}.", "")
        .removesuffix("()")
    )
    new_target = module_ir.context.get(local_name)

    if isinstance(new_target, (Func, Class)):
        ir = module_ir.get(new_target)

        # NOTE If the imported function is ignored then it will have no IR
        if ir is None:
            error.error(
                f"{_where} unable to resolve imported callable {local_name!r}"
                f" in {target.module_name!r}, it is likely ignored"
            )
            return None, None

        return new_target, ir

    if isinstance(new_target, Import):
        return resolve_import(new_target.name, new_target, imports_ir, caller)

    # NOTE
    # When reaching here the target may be a call to a method on an imported instance

    if new_target is None and "." in local_name:
        error.info(
            f"{__prefix(caller)} unable to resolve call to method "
            f"{local_name!r} in import {target.module_name!r}"
        )
        return None, None

    error.error(
        f"{__prefix(caller)} unable to resolve call to {local_name!r} in "
        f"import {target.module_name!r}"
    )
    return None, None


def get_callee_target(
    callee: Call,
    file_ir: FileIr,
    imports_ir: ImportsIr,
    caller: Func | None = None,
) -> tuple[None, None] | tuple[Func, FunctionIr]:
    """Return the func and IR of the called function."""
    # TODO Should this trigger a warning?
    if callee.target is None:
        return None, None

    if isinstance(callee.target, Builtin):
        return None, None

    if isinstance(callee.target, Func):
        return resolve_function(callee, file_ir, imports_ir, caller)

    # NOTE Procedural parameter, etc, can't be resolved
    if isinstance(callee.target, Name):
        return None, None

    if isinstance(callee.target, Class):
        return resolve_class_init(callee, file_ir, imports_ir, caller)

    if isinstance(callee.target, Import):
        return resolve_import(callee.name, callee.target, imports_ir, caller)

    raise TypeError("'callee' must be a CalleeTarget")


def partially_unbind_name(symbol: Name, new_basename: str) -> Name:
    """Return a new symbol bound to the new base name."""
    if symbol.basename == new_basename:
        return Name(symbol.name, symbol.basename)

    new_name = symbol.name
    if symbol.name.startswith("*"):
        new_name = symbol.name.replace(f"*{symbol.basename}", f"*{new_basename}", 1)
    else:
        new_name = symbol.name.replace(symbol.basename, new_basename, 1)

    return Name(new_name, new_basename)


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


def construct_swap(func: Func, call: Call) -> dict[str, str]:
    """Return the map of local function names to bound names."""
    swaps: dict[str, str] = dict()

    f_args = copy.deepcopy(func.args)

    c_args = copy.deepcopy(call.args)
    c_kwargs = copy.deepcopy(call.kwargs)

    # Python call must be ([pos_arg | *'d], ..., [named_arg | **'d], ...)
    # Python function def must be (pos_arg, ..., named_arg, ..., *'d?, **'d?)

    for target, replacement in zip(f_args, c_args):
        swaps[target] = replacement
    f_args = f_args[len(c_args) :]

    # Ensure no ambiguities
    for target in swaps.keys():
        if target not in c_kwargs.keys():
            continue

        error.fatal(f"{__prefix(func)} {target!r} given by position and name")

        return swaps

    # Allow no match as a default may be present
    for target in f_args:
        if target not in c_kwargs:
            continue
        swaps[target] = c_kwargs[target]
        del c_kwargs[target]

    if len(c_kwargs) > 0:
        error.error(f"{__prefix(func)} unexpected named arguments {c_kwargs}")

    return swaps


@dataclass
class IrDagNode:
    """Represent a function call for simplification."""

    call: Call
    func: Func
    func_ir: FunctionIr
    file_ir: FileIr
    imports_ir: ImportsIr

    def __post_init__(self) -> None:
        self.children: list[IrDagNode] = list()

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
        for callee in self.func_ir["calls"]:
            if callee in seen:
                continue

            _foc, _foc_ir = get_callee_target(
                callee, self.file_ir, self.imports_ir, self.func
            )

            # NOTE Could not find func/init (undef'd, <str>.join(), etc)
            if _foc is None or _foc_ir is None:
                continue

            self.children.append(
                IrDagNode(callee, _foc, _foc_ir, self.file_ir, self.imports_ir)
            )

            seen.add(callee)

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

        # Simplified non-terminal nodes are the combination of themselves
        # and their children partially unbound
        child_irs = [(c.simplify(), c) for c in self.children]

        simplified: FunctionIr = copy.deepcopy(self.func_ir)

        for child_ir, child in child_irs:
            swaps = construct_swap(child.func, child.call)
            unbound_child = partially_unbind(child_ir, swaps)

            simplified["sets"] |= unbound_child["sets"]
            simplified["gets"] |= unbound_child["gets"]
            simplified["dels"] |= unbound_child["dels"]

        return simplified
