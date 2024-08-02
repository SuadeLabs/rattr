"""Rattr class analyser.

Rattr is designed to be a function analyser and thus the class-based features
are rather limited.

"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from rattr import error
from rattr.analyser.base import NodeVisitor
from rattr.analyser.function import FunctionAnalyser
from rattr.analyser.types import ClassIr
from rattr.analyser.util import has_annotation, parse_rattr_results_from_annotation
from rattr.ast.util import assignment_targets, fullname_of, unravel_names
from rattr.models.context import Context
from rattr.models.ir import FunctionIr
from rattr.models.symbol import CallInterface, Class, Func, Name

if TYPE_CHECKING:
    from collections.abc import Iterator

    from rattr.ast.types import Identifier


def is_method(node: ast.stmt) -> bool:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))


def init_method_or_none(
    methods: list[ast.FunctionDef | ast.AsyncFunctionDef],
    *,
    culprit: ast.AST,
) -> ast.FunctionDef | None:
    init_methods = [method for method in methods if method.name == "__init__"]

    if len(init_methods) == 0:
        return None

    (init_method, *remainder) = init_methods

    if remainder:
        error.error("found multiple __init__ methods for class", culprit=culprit)
    if isinstance(init_method, ast.AsyncFunctionDef):
        error.fatal("found async __init__ method for class", culprit=culprit)

    return init_method


def iter_static_methods(
    methods: list[ast.FunctionDef | ast.AsyncFunctionDef],
) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    return (method for method in methods if has_annotation("staticmethod", method))


def base_names(cls: ast.ClassDef) -> list[Identifier]:
    return [fullname_of(b, safe=True) for b in cls.bases]


def is_enum_by_heuristic(cls: ast.ClassDef) -> bool:
    return any(b == "Enum" or b.endswith(".Enum") for b in base_names(cls))


def is_namedtuple_by_heuristic(cls: ast.ClassDef) -> bool:
    return any(b == "NamedTuple" or b.endswith(".NamedTuple") for b in base_names(cls))


class ClassAnalyser(NodeVisitor):
    """Walk a class's AST to determine the accessed attributes.


    TODO
        - Inheritance, super
        - Class methods
        - Methods from type
        - Nested classes

    """

    def __init__(self, _ast: ast.ClassDef, context: Context) -> None:
        """Set configuration and initialise IR."""
        self._ast = _ast
        self.name = _ast.name

        self.class_ir: ClassIr = {}

        self.context = context

    def analyse(self) -> ClassIr:
        """Entry point, return the IR produced from analysis.

        Algorithm:
            * Analyse non-method body -- i.e. class attributes, etc
                Add to context as `ClassName.attr`
                TODO Allow reference from class body context as just `attr`
            * Analyse __init__
                Add to context as Func: `ClassName`
                TODO deal with __new__, __new__ and __init__, etc
            * Analyse `@static_methods`
                Add to context as Func: `ClassName.method_name`
            * TODO Analyse `@class_methods`
            * TODO Analyse remaining methods as object methods

        """

        # NOTE
        #   Analyse within parent context, i.e. no new_context, as static
        #   methods, initialisers, should be present in the parent context
        #   just with transformed names

        statements = [stmt for stmt in self._ast.body if not is_method(stmt)]
        methods = [stmt for stmt in self._ast.body if is_method(stmt)]

        for stmt in statements:
            self.visit(stmt)

        init = init_method_or_none(methods, culprit=self._ast)  # type: ignore[reportArgumentType]

        if init is not None:
            self.visit_initialiser(init)

        # HACK Default initialisers for special cases
        if init is None:
            if is_enum_by_heuristic(self._ast):
                self.visit_enum_initialiser()

            if is_namedtuple_by_heuristic(self._ast):
                self.visit_named_tuple_initialiser()

        for method in iter_static_methods(methods):  # type: ignore[reportArgumentType]
            self.visit_static_method(method)

        return self.class_ir

    # ----------------------------------------------------------------------- #
    # Special class helpers
    # ----------------------------------------------------------------------- #

    def visit_initialiser(self, init: ast.FunctionDef) -> None:
        if has_annotation("rattr_ignore", self._ast):
            return

        new_symbol = self.symbol.with_init(init)
        self.update_symbol(new_symbol)

        if has_annotation("rattr_results", self._ast):
            self.class_ir[new_symbol] = parse_rattr_results_from_annotation(
                self._ast,
                context=self.context,
            )
            return

        init_analyser = FunctionAnalyser(init, self.context)
        self.class_ir[new_symbol] = init_analyser.analyse()

    def visit_enum_initialiser(self) -> None:
        new_symbol = self.symbol.with_init_arguments(args=("self", "_id"))
        self.update_symbol(new_symbol)

        self.class_ir[new_symbol] = {
            "sets": set(),
            "gets": {
                symbol
                for symbol in self.context.symbol_table.symbols
                if isinstance(symbol, Name)
                if symbol.name.startswith(self.prefix)
            },
            "calls": set(),
            "dels": set(),
        }

    def visit_named_tuple_initialiser(self) -> None:
        items = [
            symbol.name[len(self.prefix) :]
            for symbol in self.context.symbol_table.symbols
            if isinstance(symbol, Name)
            if symbol.name.startswith(self.prefix)
        ]

        cls = self.update_symbol(self.symbol.with_init_arguments(args=("self", *items)))
        self.class_ir[cls] = FunctionIr.the_empty_ir()

    def visit_static_method(
        self,
        method: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        qualified_name = f"{self.name}.{method.name}"

        fn = Func(
            name=qualified_name,
            token=method,
            interface=CallInterface.from_fn_def(method),
        )
        self.context.add(fn)

        method_analyser = FunctionAnalyser(method, self.context)
        self.class_ir[fn] = method_analyser.analyse()

    # ----------------------------------------------------------------------- #
    # Non-method statements
    # ----------------------------------------------------------------------- #

    def visit_AnyAssign(
        self,
        node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
    ) -> None:
        """Helper method for assignments.

        Visit ast.Assign(targets, value, type_comment)\\
        Visit ast.AnnAssign(target, annotation, value, simple)\\
        Visit ast.AugAssign(target, op, value)

        """
        names = [
            name
            for target in assignment_targets(node)
            for name in unravel_names(target)
        ]

        for name in names:
            self.context.add(Name(f"{self.name}.{name}", self.name, token=node))

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit_AnyAssign(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit_AnyAssign(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit_AnyAssign(node)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit_AnyAssign(node)

    # ----------------------------------------------------------------------- #
    # Helpers
    # ----------------------------------------------------------------------- #

    @property
    def prefix(self) -> str:
        return f"{self.name}."

    @property
    def symbol(self) -> Class:
        cls = self.context.get(self.name)

        if not isinstance(cls, Class):
            raise ValueError(f"class {self.name} is not in the current context")

        return cls

    def update_symbol(self, new_class_symbol: Class) -> Class:
        _ = self.context.pop(new_class_symbol.id)
        self.context[new_class_symbol.id] = new_class_symbol
        return new_class_symbol
