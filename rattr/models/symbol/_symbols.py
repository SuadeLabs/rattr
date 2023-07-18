from __future__ import annotations

import ast
import builtins
from importlib.machinery import ModuleSpec
from typing import TYPE_CHECKING

import attrs
from attrs import field

from rattr.models.symbol._symbol import (
    AnyCallInterface,
    CallArguments,
    CallInterface,
    Location,
    Symbol,
)
from rattr.models.symbol.util import (
    get_basename_from_name,
    get_module_name_and_spec,
    without_call_brackets,
)

if TYPE_CHECKING:
    from typing import Final, Literal

    from rattr.ast.types import AnyFunctionDef


PYTHON_LITERAL_BUILTINS: Final = ("None", "True", "False", "Ellipsis")
"""Python's literal builtin's by identifier."""

PYTHON_ATTR_ACCESS_BUILTINS: Final = ("delattr", "getattr", "hasattr", "setattr")
"""Python's builtin functions to access attributes, i.e. `getattr` etc."""

PYTHON_BUILTINS: Final = tuple(
    b
    for b in dir(builtins)
    if b not in PYTHON_LITERAL_BUILTINS
    if not b.startswith("__")
)
"""Python's callable builtins."""


@attrs.frozen
class Name(Symbol):
    name: str = field()
    basename: str = field()
    interface: CallInterface | None = field(default=None, kw_only=True)
    location: Location | None = field(default=None, kw_only=True)

    @basename.default
    def _basename_default(self) -> str:
        return get_basename_from_name(self.name)


@attrs.frozen
class Builtin(Symbol):
    name: str = field()
    interface: AnyCallInterface = field(factory=AnyCallInterface, kw_only=True)
    location: Location | None = field(default=None, kw_only=True)

    @property
    def has_affect(self) -> bool:
        return self.name in PYTHON_ATTR_ACCESS_BUILTINS


@attrs.frozen
class Import(Symbol):
    name: str = field()
    qualified_name: str = field()
    interface: AnyCallInterface = field(factory=AnyCallInterface, kw_only=True)
    location: Location | None = field(default=None, kw_only=True)

    @qualified_name.default
    def _qualified_name_default(self) -> str:
        return self.name

    @property
    def id(self) -> str:
        # We must prepend the qualified name to starred-imports or else they'd all have
        # the same name ("*")!
        if self.name == "*":
            return f"{self.qualified_name}.*"
        return self.name

    @property
    def _module_name_and_spec(self) -> tuple[str, ModuleSpec] | tuple[None, None]:
        return get_module_name_and_spec(self.qualified_name)

    @property
    def module_name(self) -> str | None:
        return self._module_name_and_spec[0]

    @property
    def module_spec(self) -> ModuleSpec | None:
        return self._module_name_and_spec[1]

    @property
    def is_import(self) -> Literal[True]:
        return True


@attrs.frozen
class Func(Symbol):
    name: str = field(converter=without_call_brackets)
    interface: CallInterface = field(kw_only=True)
    location: Location = field(factory=Location, kw_only=True)
    is_async: bool = field(default=False, kw_only=True)

    @classmethod
    def from_fn_def(cls: type[Func], fn: AnyFunctionDef) -> Func:
        """Return a new `Func` parsed from the given function def."""
        return Func(
            name=fn.name,
            interface=CallInterface.from_fn_def(fn),
            is_async=isinstance(fn, ast.AsyncFunctionDef),
        )


@attrs.frozen
class Class(Symbol):
    name: str = field(converter=without_call_brackets)
    interface: CallInterface = field(factory=AnyCallInterface, kw_only=True)
    location: Location = field(factory=Location, kw_only=True)

    def with_init(self, init: ast.FunctionDef) -> Class:
        """Return a copy of the class with the initialiser set to the given function."""
        return attrs.evolve(self, interface=CallInterface.from_fn_def(init))


@attrs.frozen
class Call(Symbol):
    name: str = field(converter=without_call_brackets)

    args: CallArguments = field(factory=CallArguments)
    target: Builtin | Import | Func | Class | None = field(default=None)

    interface: CallInterface | None = field(default=None, kw_only=True)
    location: Location | None = field(default=None, kw_only=True)

    @classmethod
    def from_call(
        cls: type[Call],
        name: str,
        call: ast.Call,
        target: Builtin | Import | Func | Class | None,
    ) -> Call:
        return Call(name=name, args=CallArguments.from_call(call), target=target)
