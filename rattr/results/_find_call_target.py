from __future__ import annotations

from typing import TYPE_CHECKING

from rattr import error
from rattr.analyser.util import is_excluded_name
from rattr.config import Config
from rattr.models.symbol import Builtin, Call, Class, Func, Import, Name
from rattr.module_locator.util import (
    derive_module_name_from_path,
    is_in_import_blacklist,
    is_in_pip,
    is_in_stdlib,
)
from rattr.results import IrTarget

if TYPE_CHECKING:
    from rattr.ast.types import Identifier
    from rattr.results import IrCall, IrEnvironment


def find_call_target_and_ir(
    call: IrCall,
    *,
    environment: IrEnvironment,
) -> IrTarget | None:
    target = call.symbol.target

    # TODO Should this trigger a warning?
    if target is None:
        return None

    if isinstance(target, Builtin):
        return None

    # Procedural parameter, etc: can't be resolved
    if isinstance(target, Name):
        return None

    if isinstance(target, Func):
        return resolve_function(call, environment=environment)

    if isinstance(target, Class):
        return resolve_class_init(call, environment=environment)

    if isinstance(target, Import):
        return resolve_import(target, environment=environment)

    raise TypeError(f"{call} is not an IrCall")


def resolve_function(
    call: IrCall,
    *,
    environment: IrEnvironment,
) -> IrTarget | None:
    if call.symbol.target is None:
        raise ImportError

    error_ = f"unable to resolve call to {call.symbol.target.name!r}"

    if call.caller is not None:
        error_ = f"{error_} in {call.caller.name!r}"

    if is_excluded_name(call.symbol.target.name):
        error.error(f"{error_}, the target matches an exclusion", culprit=call.symbol)
        return None

    try:
        target = __resolve_target_and_ir(call, environment=environment)
    except ImportError:
        if not is_call_to_method_or_member(call.symbol):
            error_ += ", the target is likely a nested function or @rattr_ignore'd"
            error.error(f"{error_}", culprit=call.symbol)
        else:
            error.info(f"{error_}", culprit=call.symbol)
        return None

    return target


def resolve_class_init(
    call: IrCall,
    *,
    environment: IrEnvironment,
) -> IrTarget | None:
    error_ = f"unable to resolve initialiser for {call.symbol.target.name!r}"

    try:
        target = __resolve_target_and_ir(call, environment=environment)
    except ImportError:
        error.error(error_, culprit=call.symbol)
        return None

    return target


def resolve_import(
    target: Import,
    *,
    environment: IrEnvironment,
) -> IrTarget | None:
    config = Config()
    arguments = config.arguments

    module_ = f"{target.module_name!r}"
    error_ = f"ignoring call to {target.name!r} imported from {{loc}}"

    if target.module_name is None:
        raise ImportError

    if is_in_import_blacklist(target.module_name):
        return None

    if not arguments.follow_local_imports:
        error.info(error_.format(loc="local module"), culprit=target)
        return None

    if not arguments.follow_pip_imports and is_in_pip(target.module_name):
        error.info(error_.format(loc=f"pip installed module {module_}"), culprit=target)
        return None

    if not arguments.follow_stdlib_imports and is_in_stdlib(target.module_name):
        error.info(error_.format(loc=f"stdlib module {module_}"), culprit=target)
        return None

    module_ir = environment.import_irs.get(target.module_name, None)

    if module_ir is None:
        raise ImportError(f"{module_} not found")

    local_name = target.name.replace(f"{target.module_name}.", "").removesuffix("()")
    new_target = module_ir.context.get(local_name)

    imported_as_ = (
        f" (imported as {target.name!r})" if target.name != local_name else ""
    )
    unresolved_ = (
        f"unable to resolve call to {local_name!r} in import {module_}{imported_as_}, "
        f"{{why}}"
    )

    if isinstance(new_target, (Func, Class)):
        ir = module_ir.get(new_target)

        # NOTE
        # If the imported function is ignored then it will have no IR
        if ir is None:
            error.error(unresolved_.format(why="it is likely ignored"), culprit=target)
            return None

        return IrTarget(symbol=new_target, ir=ir)

    if isinstance(new_target, Import):
        return resolve_import(new_target, environment=environment)

    if new_target is None and is_call_to_method_or_member(local_name):
        error.info(unresolved_.format(why="it is a method"), culprit=target)
    else:
        error.error(unresolved_.format(why="it is likely undefined"), culprit=target)

    return None


def __resolve_target_and_ir(
    call: IrCall,
    *,
    environment: IrEnvironment,
) -> IrTarget:
    if isinstance(call.symbol.target, Class):
        symbol = __resolve_real_class_target(
            call.symbol.target,
            environment=environment,
        )
    else:
        symbol = call.symbol.target

    if symbol is None:
        raise ImportError

    if symbol in environment.target_ir:
        return IrTarget(symbol=symbol, ir=environment.target_ir[symbol])

    filename = symbol.location.defined_in
    module = derive_module_name_from_path(filename)

    if module is None:
        raise ModuleNotFoundError(f"unable to find module for {str(filename)!r}")

    module_ir = environment.import_irs.get(module)

    if module_ir is None:
        raise ImportError
    if symbol not in module_ir:
        raise ImportError

    return IrTarget(symbol=symbol, ir=module_ir[symbol])


def __resolve_real_class_target(
    target: Class,
    *,
    environment: IrEnvironment,
) -> Class:
    for symbol in environment.target_ir:
        if isinstance(symbol, Class) and target.name == symbol.name:
            return symbol

    for _, import_ir in environment.import_irs.items():
        for symbol in import_ir:
            if isinstance(symbol, Class) and target.name == symbol.name:
                return symbol

    return target


def is_call_to_method_or_member(target: Call | Identifier) -> bool:
    if isinstance(target, Call):
        target = target.id
    return "." in target
