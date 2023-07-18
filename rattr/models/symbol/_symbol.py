from __future__ import annotations

import abc
from pathlib import Path
from typing import TYPE_CHECKING

import attrs
from attrs import field
from frozendict import frozendict

from rattr.config import Config
from rattr.models.symbol._util import arg_name, kwarg_name

if TYPE_CHECKING:
    import ast
    from typing import Literal

    from rattr.ast.types import AnyFunctionDef


@attrs.frozen
class Symbol(abc.ABC):
    # NOTE
    #   Derived classes should still implement the below attrs or else the editor will
    #   be unhappy. This still has utility as a declaration of interface, however.
    name: str = field()
    interface: CallInterface | None = field(default=None, kw_only=True)
    location: Location | None = field(default=None, kw_only=True)

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
        return self.location is not None

    @property
    def is_import(self) -> Literal[False]:
        return False


@attrs.frozen
class CallInterface:
    # Naming inherited from `ast.arguments`
    posonlyargs: tuple[str] = field(default=(), converter=tuple)
    args: tuple[str] = field(default=(), converter=tuple)
    kwonlyargs: tuple[str] = field(default=(), converter=tuple)

    @property
    def all(self) -> tuple[str]:
        return self.posonlyargs + self.args + self.kwonlyargs

    @classmethod
    def from_fn_def(
        cls: type[CallInterface],
        fn: ast.Lambda | AnyFunctionDef,
    ) -> CallInterface:
        """Return a new `CallInterface` parsed from the given function def."""
        if cls != CallInterface:
            raise NotImplementedError(f"not applicable to {cls.__name__}")

        return CallInterface(
            posonlyargs=[_a.arg for _a in fn.args.posonlyargs],
            args=[_arg.arg for _arg in fn.args.args],
            kwonlyargs=[_arg.arg for _arg in fn.args.kwonlyargs],
        )


@attrs.frozen
class AnyCallInterface(CallInterface):
    """Denote that the interface is unknown/unknowable; thus all calls are accepted."""


@attrs.frozen
class CallArguments:
    args: tuple[str] = field(default=(), converter=tuple)
    kwargs: frozendict[str, str] = field(default=frozendict(), converter=frozendict)

    @classmethod
    def from_call(
        cls: type[CallArguments],
        call: ast.Call,
        *,
        self: str | None = None,
    ) -> CallArguments:
        """Return a new `CallArguments` parsed from the given function call."""
        args: list[str] = [arg_name(arg) for arg in call.args]
        kwargs: dict[str, str] = {kw.arg: kwarg_name(kw) for kw in call.keywords}

        if self is not None:
            args = [self, *args]

        return CallArguments(args=args, kwargs=kwargs)


@attrs.frozen
class Location:
    _derived_location: Path = field(kw_only=True)

    @_derived_location.default
    def _defined_in_default(self) -> str:
        config = Config()
        file = config.state.current_file

        if file is None:
            raise ValueError("unable to derive location (current file is None)")

        return file

    @property
    def defined_in(self) -> Path:
        return self._derived_location
