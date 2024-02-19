from __future__ import annotations

import abc
import ast
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import attrs
from attrs import field
from frozendict import frozendict

from rattr.config.util import get_current_file
from rattr.models.symbol._util import PYTHON_BUILTINS_LOCATION, arg_name, kwarg_name

if TYPE_CHECKING:
    from typing import Literal

    from rattr.ast.types import Identifier


@attrs.frozen
class Symbol(abc.ABC):
    name: str = field()

    token: ast.AST | None = field(default=None, kw_only=True, hash=False, eq=False)
    location: Location | None = field(default=None, kw_only=True, hash=False, eq=False)

    interface: CallInterface | None = field(default=None, kw_only=True)

    def __attrs_pre_init__(self) -> None:
        if type(self) == Symbol:
            raise NotImplementedError("symbol should be sub-classed")

    @property
    def id(self) -> str:
        # For most symbols the name is already the identifier, but for starred-imports
        # we must prepend the qualified name to avoid namespace collisions.
        # See: Import.id(...)
        return self.name

    @property
    def is_callable(self) -> bool:
        return self.interface is not None

    @property
    def has_location(self) -> bool:
        return (
            self.location is not None
            and str(self.location.defined_in) != PYTHON_BUILTINS_LOCATION
        )

    @property
    def is_import(self) -> Literal[False]:
        return False


class ConsumableCallInterface(NamedTuple):
    posonlyargs: list[Identifier]
    args: list[Identifier]
    vararg: Identifier | None
    kwonlyargs: list[Identifier]
    kwarg: Identifier | None


@attrs.frozen
class CallInterface:
    # Naming inherited from `ast.arguments`
    posonlyargs: tuple[str] = field(default=(), converter=tuple)
    args: tuple[str] = field(default=(), converter=tuple)
    vararg: str | None = field(default=None)
    kwonlyargs: tuple[str] = field(default=(), converter=tuple)
    kwarg: str | None = field(default=None)

    @property
    def all(self) -> tuple[str]:
        arguments: list[str] = []

        arguments += self.posonlyargs
        arguments += self.args

        if self.vararg is not None:
            arguments.append(self.vararg)

        arguments += self.kwonlyargs

        if self.kwarg is not None:
            arguments.append(self.kwarg)

        return tuple(arguments)

    @classmethod
    def from_fn_def(
        cls: type[CallInterface],
        fn: ast.Lambda | ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> CallInterface:
        """Return a new `CallInterface` parsed from the given function def."""
        return cls.from_arguments(fn.args)

    @classmethod
    def from_arguments(
        cls: type[CallInterface],
        arguments: ast.arguments,
    ) -> CallInterface:
        """Return a new `CallInterface` parsed from the given arguments."""
        if isinstance(_vararg := arguments.vararg, ast.arg):
            vararg = _vararg.arg
        else:
            vararg = None

        if isinstance(_kwarg := arguments.kwarg, ast.arg):
            kwarg = _kwarg.arg
        else:
            kwarg = None

        return CallInterface(
            posonlyargs=[_a.arg for _a in arguments.posonlyargs],
            args=[_arg.arg for _arg in arguments.args],
            vararg=vararg,
            kwonlyargs=[_arg.arg for _arg in arguments.kwonlyargs],
            kwarg=kwarg,
        )

    def as_consumable_call_interface(self) -> ConsumableCallInterface:
        """Return a copy of this interface as a consumable named tuple.

        This is s.t. the caller can freely `pop` or otherwise destructively consume the
        interface at the point of call.
        """
        return ConsumableCallInterface(
            posonlyargs=[arg for arg in self.posonlyargs],
            args=[arg for arg in self.args],
            vararg=self.vararg,
            kwonlyargs=[kwarg for kwarg in self.kwonlyargs],
            kwarg=self.kwarg,
        )


@attrs.frozen
class AnyCallInterface(CallInterface):
    """Denote that the interface is unknown/unknowable; thus all calls are accepted."""

    @classmethod
    def from_fn_def(
        cls: type[CallInterface],
        fn: ast.Lambda | ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> CallInterface:
        if cls != CallInterface:
            raise NotImplementedError(f"not applicable to {cls.__name__}")

    @classmethod
    def from_arguments(
        cls: type[CallInterface],
        arguments: ast.arguments,
    ) -> CallInterface:
        if cls != CallInterface:
            raise NotImplementedError(f"not applicable to {cls.__name__}")


@attrs.frozen
class CallArguments:
    args: tuple[str] = field(default=(), converter=tuple)
    kwargs: frozendict[str, str] = field(factory=frozendict, converter=frozendict)

    @classmethod
    def from_call(
        cls: type[CallArguments],
        call: ast.Call,
        *,
        self: Identifier | None = None,
    ) -> CallArguments:
        """Return a new `CallArguments` parsed from the given function call."""
        args: list[str] = [arg_name(arg) for arg in call.args]
        kwargs: dict[str, str] = {kw.arg: kwarg_name(kw) for kw in call.keywords}

        if self is not None:
            args = [self, *args]

        return CallArguments(args=args, kwargs=kwargs)


@attrs.frozen
class Location:
    token: ast.AST | None = field(default=None)
    _file: Path = field(alias="file", factory=get_current_file, kw_only=True)

    @property
    def file(self) -> Path:
        return self._file

    @property
    def lineno(self) -> int | None:
        if self.token is None:
            return None
        return self.token.lineno

    @property
    def end_lineno(self) -> int | None:
        if self.token is None:
            return None
        return self.token.end_lineno

    @property
    def col_offset(self) -> int | None:
        if self.token is None:
            return None
        return self.token.col_offset

    @property
    def end_col_offset(self) -> int | None:
        if self.token is None:
            return None
        return self.token.end_col_offset

    @property
    def defined_in(self) -> Path:
        return self._file
