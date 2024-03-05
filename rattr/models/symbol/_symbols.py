from __future__ import annotations

import ast
import builtins
from pathlib import Path
from typing import TYPE_CHECKING, Union

import attrs
from attrs import field

from rattr.codegen import gen_import_from_stmt
from rattr.models.symbol._symbol import (
    AnyCallInterface,
    CallArguments,
    CallInterface,
    Location,
    Symbol,
)
from rattr.models.symbol.util import (
    PYTHON_BUILTINS_LOCATION,
    get_basename_from_name,
    without_call_brackets,
)
from rattr.module_locator.models import ModuleSpec
from rattr.module_locator.util import find_module_name_and_spec

if TYPE_CHECKING:
    from typing import Final, Literal

    from rattr.ast.types import Identifier
    from rattr.module_locator.util import ModuleName


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

PYTHON_NON_PRIMITIVE_RETURNING_BUILTINS: Final = frozenset(
    (
        "eval",
        "exec",
        "getattr",
        "iter",
        "next",
        "slice",
        "super",
        "type",
    )
)
"""Python's builtins may-or-will return a non-primitive."""


@attrs.frozen
class Name(Symbol):
    name: str = field()
    basename: str = field()

    token: Union[ast.AST, None] = field(
        default=None,
        kw_only=True,
        hash=False,
        eq=False,
    )
    location: Location = field(kw_only=True, hash=False, eq=False)

    interface: Union[CallInterface, None] = field(default=None, kw_only=True)

    @basename.default
    def _basename_default(self) -> str:
        return get_basename_from_name(self.name)

    @location.default
    def _location_default(self) -> Location:
        if self.token is None:
            return Location(lineno=1, col_offset=0)
        return Location.from_ast_token(self.token)


@attrs.frozen
class Builtin(Symbol):
    name: str = field()

    token: Union[ast.AST, None] = field(
        default=None,
        kw_only=True,
        hash=False,
        eq=False,
    )
    location: Location = field(kw_only=True, hash=False, eq=False)

    interface: AnyCallInterface = field(factory=AnyCallInterface, kw_only=True)

    @location.default
    def _location_default(self) -> Location:
        file = Path(PYTHON_BUILTINS_LOCATION)

        if self.token is None:
            return Location(lineno=1, col_offset=0, file=file)

        return Location.from_ast_token(self.token, file=file)

    @property
    def has_affect(self) -> bool:
        return self.name in PYTHON_ATTR_ACCESS_BUILTINS


@attrs.frozen
class Import(Symbol):
    name: str = field()
    qualified_name: str = field()

    token: Union[ast.AST, None] = field(
        default=None,
        kw_only=True,
        hash=False,
        eq=False,
    )
    location: Location = field(kw_only=True, hash=False, eq=False)

    interface: AnyCallInterface = field(factory=AnyCallInterface, kw_only=True)

    @qualified_name.default
    def _qualified_name_default(self) -> str:
        return self.name

    @location.default
    def _location_default(self) -> Location:
        if self.token is None:
            return Location(lineno=1, col_offset=0)
        return Location.from_ast_token(self.token)

    @property
    def id(self) -> str:
        # We must prepend the qualified name to starred-imports or else they'd all have
        # the same name ("*")!
        if self.name == "*":
            return f"{self.qualified_name}.*"
        return self.name

    @property
    def _module_name_and_spec(
        self,
    ) -> tuple[ModuleName, ModuleSpec] | tuple[None, None]:
        return find_module_name_and_spec(self.qualified_name)

    @property
    def module_name(self) -> ModuleName | None:
        return self._module_name_and_spec[0]

    @property
    def module_spec(self) -> ModuleSpec | None:
        return self._module_name_and_spec[1]

    @property
    def is_import(self) -> Literal[True]:
        return True

    @property
    def origin(self) -> Path | None:
        if self.module_spec is None:
            return None

        if self.module_spec.origin is None:
            return None

        return Path(self.module_spec.origin).resolve()

    def code(self) -> str:
        # NOTE Derive from `self.qualified_name` as `self.module_name` can be `None`
        module = self.qualified_name.replace(f".{self.name}", "")
        return gen_import_from_stmt(module, self.name)


@attrs.frozen
class Func(Symbol):
    name: str = field(converter=without_call_brackets)

    token: Union[ast.AST, None] = field(
        default=None,
        kw_only=True,
        hash=False,
        eq=False,
    )
    location: Location = field(kw_only=True, hash=False, eq=False)

    interface: CallInterface = field(kw_only=True)

    is_async: bool = field(default=False, kw_only=True)

    @location.default
    def _location_default(self) -> Location:
        if self.token is None:
            return Location(lineno=1, col_offset=0)
        return Location.from_ast_token(self.token)

    @classmethod
    def from_fn_def(
        cls: type[Func],
        fn: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> Func:
        """Return a new `Func` parsed from the given function def."""
        return Func(
            name=fn.name,
            token=fn,
            interface=CallInterface.from_fn_def(fn),
            is_async=isinstance(fn, ast.AsyncFunctionDef),
        )


@attrs.frozen
class Class(Symbol):
    name: str = field(converter=without_call_brackets)

    token: Union[ast.AST, None] = field(
        default=None,
        kw_only=True,
        hash=False,
        eq=False,
    )
    location: Location = field(kw_only=True, hash=False, eq=False)

    interface: CallInterface = field(factory=AnyCallInterface, kw_only=True)

    @location.default
    def _location_default(self) -> Location:
        if self.token is None:
            return Location(lineno=1, col_offset=0)
        return Location.from_ast_token(self.token)

    def with_init(self, init: ast.FunctionDef) -> Class:
        """Return a copy of the class with the initialiser set to the given function."""
        return attrs.evolve(self, interface=CallInterface.from_fn_def(init))

    def with_init_arguments(
        self,
        *,
        posonlyargs: tuple[str, ...] = (),
        args: tuple[str, ...] = (),
        vararg: str | None = None,
        kwonlyargs: tuple[str, ...] = (),
        kwarg: str | None = None,
    ) -> Class:
        return attrs.evolve(
            self,
            interface=CallInterface(
                posonlyargs=posonlyargs,
                args=args,
                vararg=vararg,
                kwonlyargs=kwonlyargs,
                kwarg=kwarg,
            ),
        )

    def with_init_interface(self, interface: CallInterface) -> Class:
        return attrs.evolve(self, interface=interface)

    @classmethod
    def from_class_def(cls: type[Class], ast_class: ast.ClassDef) -> None:
        """Return a new `Class` parsed from the given class def."""
        init_interface = AnyCallInterface()

        for stmt in ast_class.body:
            if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            if stmt.name != "__init__":
                continue

            init_interface = CallInterface.from_fn_def(stmt)

        return Class(name=ast_class.name, token=ast_class, interface=init_interface)


@attrs.frozen
class Call(Symbol):
    name: str = field(converter=without_call_brackets)

    args: CallArguments = field(factory=CallArguments)
    target: Union[Builtin, Import, Func, Class, Name, None] = field(default=None)

    token: Union[ast.AST, None] = field(
        default=None,
        kw_only=True,
        hash=False,
        eq=False,
    )
    location: Location = field(kw_only=True, hash=False, eq=False)

    interface: Union[CallInterface, None] = field(
        init=False,
        default=None,
        kw_only=True,
    )

    @location.default
    def _location_default(self) -> Location:
        if self.token is None:
            return Location(lineno=1, col_offset=0)
        return Location.from_ast_token(self.token)

    @classmethod
    def from_call(
        cls: type[Call],
        name: str,
        call: ast.Call,
        target: Builtin | Import | Func | Class | None,
        *,
        self: Identifier | None = None,
    ) -> Call:
        return Call(
            name=name,
            args=CallArguments.from_call(call, self=self),
            target=target,
            token=call,
        )

    @property
    def name_of_call(self) -> str:
        return f"{self.name}()"
