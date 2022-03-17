"""Represent the IR of functions as a DAG, for simplification."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Union

from rattr import config, error
from rattr.analyser.context import (
    Builtin,
    Call,
    Class,
    Func,
    Import,
    Name,
    Symbol,
)
from rattr.analyser.types import FileIR, FunctionIR, ImportsIR
from rattr.analyser.util import (
    is_blacklisted_module,
    is_excluded_name,
    is_pip_module,
    is_stdlib_module,
    module_name_from_file_path,
    remove_call_brackets,
)


def __prefix(func: Func) -> str:
    """HACK We no longer have `culprit` so manually construct prefix."""
    if func is None:
        return ""

    if func.defined_in is not None and config.show_path:
        file = error.format_path(func.defined_in)
    else:
        file = ""

    return "\033[1m{}:\033[0m".format(file)


def __resolve_target_and_ir(
    callee: Call,
    file_ir: FileIR,
    imports_ir: ImportsIR,
) -> Tuple[Func, FunctionIR]:
    """Helper function for `resolve_function` and `resolve_class`."""
    if callee.target in file_ir:
        return callee.target, file_ir[callee.target]

    filename = callee.target.defined_in
    module = module_name_from_file_path(filename)

    if module is None:
        raise ModuleNotFoundError(f"unable to find module for '{filename}'")

    module_ir = imports_ir.get(module)

    if module_ir is None:
        raise ImportError

    if callee.target not in module_ir:
        raise ImportError

    return callee.target, module_ir[callee.target]


def resolve_function(
    callee: Call,
    file_ir: FileIR,
    imports_ir: ImportsIR,
    caller: Optional[Func] = None,
) -> Union[Tuple[None, None], Tuple[Func, FunctionIR]]:
    _msg = f"{__prefix(caller)} unable to resolve call to " f"'{callee.target.name}'"

    if caller is not None:
        _msg = f"{_msg} in '{caller.name}'"

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


def resolve_class(
    callee: Call,
    file_ir: FileIR,
    imports_ir: ImportsIR,
    caller: Optional[Func] = None,
) -> Union[Tuple[None, None], Tuple[Func, FunctionIR]]:
    _where = __prefix(caller)

    try:
        cls, ir = __resolve_target_and_ir(callee, file_ir, imports_ir)
    except ImportError:
        error.error(f"{_where} unable to resolve initialiser for '{callee.name}'")
        return None, None

    return cls, ir


def resolve_import(
    name: str,
    target: Import,
    imports_ir: ImportsIR,
    caller: Optional[Func] = None,
) -> Union[Tuple[None, None], Tuple[Func, FunctionIR]]:
    """Return the `Func` and IR for the given import."""
    _where = __prefix(caller)

    module = target.module_name
    module_ir: FileIR = imports_ir.get(module, None)

    as_name, qualified_name = target.name, target.qualified_name

    if is_blacklisted_module(module):
        return None, None

    if not config.follow_imports:
        error.info(f"{_where} ignoring call to imported function '{target.name}'")
        return None, None

    if not config.follow_pip_imports and is_pip_module(module):
        error.info(
            f"{_where} ignoring call to function '{target.name}' imported "
            f"from pip installed module '{module}'"
        )
        return None, None

    if not config.follow_stdlib_imports and is_stdlib_module(module):
        error.info(
            f"{_where} ignoring call to function '{target.name}' imported "
            f"from stdlib module '{module}'"
        )
        return None, None

    if module is None:
        raise ValueError(f"Target {target.name} has no module name")

    if module_ir is None:
        raise ImportError(f"Import '{module}' not found")

    local_name = name.replace(as_name, qualified_name).replace(f"{module}.", "")
    local_name = remove_call_brackets(local_name)

    new_target: Optional[Symbol] = module_ir.context.get(local_name)
    if isinstance(new_target, (Func, Class)):
        ir = module_ir.get(new_target)

        # NOTE If the imported function is ignored then it will have no IR
        if ir is None:
            error.error(
                f"{_where} unable to resolve imported callable '{local_name}'"
                f" in '{module}', it is likely ignored"
            )
            return None, None

        return new_target, ir

    if isinstance(new_target, Import):
        return resolve_import(new_target.name, new_target, imports_ir, caller)

    # NOTE
    #   When reaching here the target may be a call to a method on an imported
    #   instance

    if new_target is None and "." in local_name:
        error.info(
            f"{__prefix(caller)} unable to resolve call to method "
            f"'{local_name}' in import '{module}'"
        )
        return None, None

    error.error(
        f"{__prefix(caller)} unable to resolve call to '{local_name}' in "
        f"import '{module}'"
    )
    return None, None


def get_callee_target(
    callee: Call,
    file_ir: FileIR,
    imports_ir: ImportsIR,
    caller: Optional[Func] = None,
) -> Union[Tuple[None, None], Tuple[Func, FunctionIR]]:
    """Return the `Symbol` and IR of the called function."""
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
        return resolve_class(callee, file_ir, imports_ir, caller)

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


def partially_unbind(func_ir: FunctionIR, swaps: Dict[str, str]) -> FunctionIR:
    """Return the partially unbound results for the given function."""
    return {
        "sets": {
            partially_unbind_name(n, swaps.get(n.basename, n.basename))
            for n in func_ir["sets"]
        },
        "gets": {
            partially_unbind_name(n, swaps.get(n.basename, n.basename))
            for n in func_ir["gets"]
        },
        "dels": {
            partially_unbind_name(n, swaps.get(n.basename, n.basename))
            for n in func_ir["dels"]
        },
        "calls": func_ir["calls"],
    }


def construct_swap(func: Func, call: Call) -> Dict[str, str]:
    """Return the map of local function names to bound names."""
    swaps: Dict[str, str] = dict()

    f_args = deepcopy(func.args)

    c_args = deepcopy(call.args)
    c_kwargs = deepcopy(call.kwargs)

    # Python call must be ([pos_arg | *'d], ..., [named_arg | **'d], ...)
    # Python function def must be (pos_arg, ..., named_arg, ..., *'d?, **'d?)

    for target, replacement in zip(f_args, c_args):
        swaps[target] = replacement
    f_args = f_args[len(c_args) :]

    # Ensure no ambiguities
    for target in swaps.keys():
        if target not in c_kwargs.keys():
            continue

        error.fatal(f"{__prefix(func)} '{target}' given by position and name")

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
    func_ir: FunctionIR
    file_ir: FileIR
    imports_ir: ImportsIR

    def __post_init__(self) -> None:
        self.children: List[IrDagNode] = list()

    def populate(self, seen: Optional[Set[Call]] = None) -> Set[Call]:
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

    def simplify(self) -> FunctionIR:
        """Return the IR modified to include dependent calls.

        NOTE
            Assumes that the root IrDagNode has been populated via `populate`!

        """
        # Leafs are already simplified
        if len(self.children) == 0:
            return deepcopy(self.func_ir)

        # Simplified non-terminal nodes are the combination of themselves
        # and their children partially unbound
        child_irs = [(c.simplify(), c) for c in self.children]

        simplified: FunctionIR = deepcopy(self.func_ir)

        for child_ir, child in child_irs:
            swaps = construct_swap(child.func, child.call)
            unbound_child = partially_unbind(child_ir, swaps)

            simplified["sets"] = simplified["sets"].union(unbound_child["sets"])

            simplified["gets"] = simplified["gets"].union(unbound_child["gets"])

            simplified["dels"] = simplified["dels"].union(unbound_child["dels"])

        return simplified
