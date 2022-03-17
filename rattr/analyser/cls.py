"""Rattr class analyser.

Rattr is designed to be a function analyser and thus the class-based features
are rather limited.

"""

import ast
from typing import List

from rattr.analyser.base import NodeVisitor
from rattr.analyser.context import Context
from rattr.analyser.context.symbol import Class, Func, Name, Symbol
from rattr.analyser.function import FunctionAnalyser
from rattr.analyser.types import AnyAssign, AnyFunctionDef, ClassIR, FunctionIR
from rattr.analyser.util import (
    get_assignment_targets,
    get_fullname,
    get_function_def_args,
    has_annotation,
    unravel_names,
)


def is_method(node: ast.AST) -> bool:
    return isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))


def get_statements(statements: ast.AST) -> List[AnyFunctionDef]:
    return list(filter(lambda stmt: not is_method(stmt), statements))


def get_methods(statements: ast.AST) -> List[ast.stmt]:
    return list(filter(lambda stmt: is_method(stmt), statements))


def get_initialiser(methods: List[AnyFunctionDef]) -> AnyFunctionDef:
    init = list(filter(lambda m: m.name == "__init__", methods))

    if len(init) == 0:
        return None

    return init[0]


def get_static_methods(methods: List[AnyFunctionDef]) -> AnyFunctionDef:
    return filter(lambda m: has_annotation("staticmethod", m), methods)


def get_base_names(cls: ast.ClassDef) -> List[str]:
    return list(map(lambda b: get_fullname(b, safe=True), cls.bases))


def is_enum(cls: ast.ClassDef) -> bool:
    # NOTE Purely heuristic, though it does allow for user defined Enum bases
    return any(n == "Enum" or n.endswith(".Enum") for n in get_base_names(cls))


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
        if not isinstance(_ast, ast.ClassDef):
            raise TypeError("ClassAnalyser expects `_ast` to be a class")

        self._ast = _ast
        self.class_name = _ast.name

        self.class_ir: ClassIR = dict()

        # NOTE Managed by `new_context` contextmanager -- do not manually set
        self.context = context

    def analyse(self) -> ClassIR:
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

        statements = get_statements(self._ast.body)
        methods = get_methods(self._ast.body)

        # Visit statements
        for stmt in statements:
            self.visit(stmt)

        # Visit initialiser
        init = get_initialiser(methods)

        if init is not None:
            self.visit_initialiser(init)

        # NOTE TODO Handle with proper inheritance
        if init is None and is_enum(self._ast):
            self.visit_enum_initialiser()

        # Visit static methods
        for method in get_static_methods(methods):
            self.visit_static_method(method)

        return self.class_ir

    # ----------------------------------------------------------------------- #
    # Non-method statements
    # ----------------------------------------------------------------------- #

    def visit_initialiser(self, init: AnyFunctionDef) -> None:
        # NOTE
        #   Class already in context (as Class("ClassName"))
        #   Add initialiser as Func("ClassName.__init__")
        #   On resolving call with target Class("ClassName") look for
        #   Func("ClassName.__init__", ...)
        cls: Class = self.context.get(self.class_name)

        # Update the class symbol with __init__'s arguments
        # See: context/symbol.py::Class
        # See: context/context.py::RootContext.register_ClassDef
        cls.args, cls.vararg, cls.kwarg = get_function_def_args(init)

        self.class_ir[cls] = FunctionAnalyser(init, self.context).analyse()

    def visit_enum_initialiser(self) -> None:
        cls: Class = self.context.get(self.class_name)
        cls.args, cls.vararg, cls.kwarg = (
            [
                "self",
                "_id",
            ],
            None,
            None,
        )

        # NOTE Can't determine result at compile-time, thus give every option
        symbols = self.context.symbol_table.symbols()
        names: List[Symbol] = list(filter(lambda s: isinstance(s, Name), symbols))
        enum_values = filter(lambda n: n.name.startswith(f"{self.class_name}."), names)

        ir: FunctionIR = {
            "sets": set(),
            "gets": set(enum_values),
            "calls": set(),
            "dels": set(),
        }

        self.class_ir[cls] = ir

    def visit_static_method(self, method: AnyFunctionDef) -> None:
        qualified_name = f"{self.class_name}.{method.name}"
        fn = Func(qualified_name, *get_function_def_args(method))

        self.class_ir[fn] = FunctionAnalyser(method, self.context).analyse()

    # ----------------------------------------------------------------------- #
    # Non-method statements
    # ----------------------------------------------------------------------- #

    def visit_AnyAssign(self, node: AnyAssign) -> None:
        """Helper method for assignments.

        Visit ast.Assign(targets, value, type_comment)\\
        Visit ast.AnnAssign(target, annotation, value, simple)\\
        Visit ast.AugAssign(target, op, value)

        """
        targets = get_assignment_targets(node)
        names = [name for target in targets for name in unravel_names(target)]

        for name in names:
            name = Name(f"{self.class_name}.{name}", self.class_name)
            self.context.add(name)

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit_AnyAssign(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit_AnyAssign(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit_AnyAssign(node)
