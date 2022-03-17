"""Base classes for Rattr components."""

import ast
from abc import ABCMeta, abstractmethod, abstractproperty
from ast import NodeTransformer, NodeVisitor  # noqa: F401
from itertools import product
from typing import Dict, List, Optional

from rattr import error
from rattr.analyser.context import Context
from rattr.analyser.context.symbol import Import
from rattr.analyser.types import FuncOrAsyncFunc, FunctionIR


class Assertor(NodeVisitor):
    """Assertor base class.

    An assertor can either be strict or non-strict, set by the constructor
    argument `is_strict`, having the following affect:
        is_strict:
            on condition failure, log fatal error (halts execution)
        not is_strict:
            on condition failure, log warning

    """

    def __init__(self, is_strict: bool = True) -> None:
        self.is_strict: bool = is_strict
        self.context: Context = None

    def assert_holds(self, node: ast.AST, context: Context) -> None:
        """Entry point for an Assertor, visit the tree to assert properties."""
        self.context = context

        super().visit(node)

    def failed(self, message: str, culprit: Optional[ast.AST] = None) -> None:
        """Handle assertion failure."""
        if self.is_strict:
            handler = error.fatal
        else:
            handler = error.warning

        handler(message, culprit)


class CustomFunctionAnalyser(NodeVisitor, metaclass=ABCMeta):
    """Base class for a custom function visitor."""

    @abstractproperty
    def name(self) -> str:
        """Return the name of the function handled by this analyser."""
        return ""

    @abstractproperty
    def qualified_name(self) -> str:
        """Return the qualified name of the function."""
        return ""

    @abstractmethod
    def on_def(self, name: str, node: FuncOrAsyncFunc, ctx: Context) -> FunctionIR:
        """Return the IR of the definition of the handled function."""
        return {
            "sets": set(),
            "gets": set(),
            "dels": set(),
            "calls": set(),
        }

    @abstractmethod
    def on_call(self, name: str, node: ast.Call, ctx: Context) -> FunctionIR:
        """Return the IR produced by a call to the handled function.

        The returned IR will be union'd with the IR of the caller function.

        Argument `fna` is the FunctionAnalyser instance that the call is from.

        """
        return {
            "sets": set(),
            "gets": set(),
            "dels": set(),
            "calls": set(),
        }


class CustomFunctionHandler:
    """Dispatch to CustomFunctionAnalyser.

    If a builtin and user-defined function have the same name, then the builtin
    function analyser will take precedence.

    Initialiser:
        Register the given builtin and user-defined custom function analysers.

    """

    def __init__(
        self,
        builtins: Optional[List[CustomFunctionAnalyser]] = None,
        user_defined: Optional[List[CustomFunctionAnalyser]] = None,
    ) -> None:
        self._builtins: Dict[str, CustomFunctionAnalyser] = dict()
        self._user_def: Dict[str, CustomFunctionAnalyser] = dict()

        for analyser in builtins or []:
            self._builtins[analyser.name] = analyser

        for analyser in user_defined or []:
            self._user_def[analyser.name] = analyser

    def __get_by_name(self, name: str) -> Optional[CustomFunctionAnalyser]:
        analyser = None

        if name in self._user_def:
            analyser = self._user_def[name]

        if name in self._builtins:
            analyser = self._builtins[name]

        return analyser

    def __get_by_symbol(
        self, name: str, ctx: Context
    ) -> Optional[CustomFunctionAnalyser]:
        symbols: List[Import] = list()

        _imports: filter[Import] = filter(
            lambda s: isinstance(s, Import), ctx.symbol_table.symbols()
        )

        for symbol in _imports:
            # From imported
            if name in (symbol.name, symbol.qualified_name):
                symbols.append(symbol)

            # Module imported
            if name.startswith(f"{symbol.name}."):
                symbols.append(symbol)

        for symbol, analyser in product(symbols, self._user_def.values()):
            # From imported
            if analyser.qualified_name == symbol.qualified_name:
                return analyser

            # Module imported
            if analyser.qualified_name == name.replace(
                symbol.name, symbol.qualified_name
            ):
                return analyser

        return None

    def get(self, name: str, ctx: Context) -> Optional[CustomFunctionAnalyser]:
        """Return the analyser for the function `name`, `None` otherwise."""
        analyser = self.__get_by_name(name)

        if analyser is None:
            analyser = self.__get_by_symbol(name, ctx)

        return analyser

    def has_analyser(self, name: str, ctx: Context) -> bool:
        """Return `True` if there is a analyser for the function `name`."""
        return self.get(name, ctx) is not None

    def handle_def(self, name: str, node: FuncOrAsyncFunc, ctx: Context) -> FunctionIR:
        """Dispatch to the to the appropriate analyser."""
        analyser = self.get(name, ctx)

        if analyser is None:
            raise ValueError

        return analyser.on_def(name, node, ctx)

    def handle_call(self, name: str, node: ast.Call, ctx: Context) -> FunctionIR:
        """Dispatch to the to the appropriate analyser."""
        analyser = self.get(name, ctx)

        if analyser is None:
            raise ValueError

        return analyser.on_call(name, node, ctx)
