from __future__ import annotations

from typing import TYPE_CHECKING

import attrs
from attrs import field

from rattr.analyser.base import Assertor, CustomFunctionAnalyser
from rattr.config import Config
from rattr.models.symbol import Builtin, Import, Symbol
from rattr.plugins.analysers import DEFAULT_FUNCTION_ANALYSERS

if TYPE_CHECKING:
    from collections.abc import Iterable

    from rattr.ast.types import FullyQualifiedName, Identifier, ModuleName


@attrs.mutable
class Plugins:
    _assertors: list[Assertor] = field(alias="assertors", converter=list)
    _analysers: list[CustomFunctionAnalyser] = field(alias="analysers", converter=list)

    _analysers_by_fully_qualified_name: dict[
        FullyQualifiedName,
        CustomFunctionAnalyser,
    ] = field(init=False)

    @property
    def assertors(self) -> list[Assertor]:
        return self._assertors

    @property
    def analysers(self) -> list[CustomFunctionAnalyser]:
        return self._analysers

    @_analysers_by_fully_qualified_name.default
    def set_analysers_by_fully_qualified_name(self) -> None:
        return {analyser.qualified_name: analyser for analyser in self.analysers}

    def register_assertors(
        self,
        new_assertors: Iterable[Assertor],
    ) -> None:
        self._assertors = list(set(self._assertors) | set(new_assertors))

    def register_analysers(
        self,
        new_analysers: Iterable[CustomFunctionAnalyser],
    ) -> None:
        self._analysers = list(set(self._analysers) | set(new_analysers))
        self._analysers_by_fully_qualified_name = {
            analyser.qualified_name: analyser for analyser in self._analysers
        }

    def has_analyser(
        self,
        target: Symbol | None,
        *,
        modulename: ModuleName | None = None,
    ) -> bool:
        return self.get_analyser(target, modulename=modulename) is not None

    def get_analyser(
        self,
        target: Symbol | None,
        *,
        modulename: ModuleName | None = None,
    ) -> CustomFunctionAnalyser | None:
        if target is None:
            return None

        qualified_name = derive_qualified_name(target, modulename=modulename)

        if qualified_name in self._analysers_by_fully_qualified_name:
            return self._analysers_by_fully_qualified_name[qualified_name]

        return None


plugins = Plugins(assertors=[], analysers=DEFAULT_FUNCTION_ANALYSERS)


def register_rattr_plugins(
    *,
    assertors: Iterable[Assertor] = (),
    analysers: Iterable[CustomFunctionAnalyser] = (),
) -> None:
    """Configure the global rattr plugins.

    This should be called exactly once during custom rattr setup. If not called this
    remains default.
    """
    global plugins

    plugins.register_assertors(assertors)
    plugins.register_analysers(analysers)


def register_rattr_module_blacklist_patterns(*terms: ModuleName) -> None:
    """Register additional module blacklist terms."""
    config = Config()

    for term in terms:
        config.PLUGINS_BLACKLIST_PATTERNS.add(term)


def derive_qualified_name(
    symbol: Symbol,
    *,
    modulename: ModuleName | None = None,
) -> Identifier:
    if isinstance(symbol, Builtin):
        return symbol.id

    if isinstance(symbol, Import):
        return symbol.qualified_name

    if modulename is not None:
        return f"{modulename}.{symbol.id}"

    return symbol.id
