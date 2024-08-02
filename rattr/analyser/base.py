"""Base classes for Rattr components."""
from __future__ import annotations

import ast
from abc import ABCMeta, abstractmethod
from ast import NodeVisitor
from typing import TYPE_CHECKING

from rattr import error
from rattr.analyser.types import FunctionIr
from rattr.models.context import Context

if TYPE_CHECKING:
    from rattr.ast.types import Identifier


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

    def assert_holds(self, node: ast.AST, context: Context) -> None:
        """Entry point for an Assertor, visit the tree to assert properties."""
        self.context = context

        super().visit(node)

    def failed(self, message: str, culprit: ast.AST | None = None) -> None:
        """Handle assertion failure."""
        if self.is_strict:
            handler = error.fatal
        else:
            handler = error.warning

        handler(message, culprit)


class CustomFunctionAnalyser(NodeVisitor, metaclass=ABCMeta):
    """Base class for a custom function visitor."""

    @property
    @abstractmethod
    def name(self) -> Identifier:
        """Return the name of the function handled by this analyser."""
        return ""

    @property
    @abstractmethod
    def qualified_name(self) -> Identifier:
        """Return the qualified name of the function."""
        return ""

    @abstractmethod
    def on_def(
        self,
        name: Identifier,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        ctx: Context,
    ) -> FunctionIr:
        """Return the IR of the definition of the handled function."""
        return FunctionIr.the_empty_ir()

    @abstractmethod
    def on_call(self, name: Identifier, node: ast.Call, ctx: Context) -> FunctionIr:
        """Return the IR produced by a call to the handled function.

        The returned IR will be union'd with the IR of the caller function.

        Argument `fna` is the FunctionAnalyser instance that the call is from.

        """
        return FunctionIr.the_empty_ir()
