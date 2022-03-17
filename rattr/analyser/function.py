"""Rattr function analyser."""

import ast
from itertools import accumulate
from typing import List, Optional, Tuple

from rattr import error
from rattr.analyser.base import NodeVisitor
from rattr.analyser.context import (
    Call,
    Class,
    Context,
    Func,
    Name,
    Symbol,
    new_context,
)
from rattr.analyser.types import (
    AnyAssign,
    AnyFunctionDef,
    CompoundStrictlyNameable,
    FunctionIR,
    Nameable,
    StrictlyNameable,
)
from rattr.analyser.util import (
    LOCAL_VALUE_PREFIX,
    PYTHON_ATTR_BUILTINS,
    assignment_is_one_to_one,
    class_in_rhs,
    get_assignment_targets,
    get_basename,
    get_basename_fullname_pair,
    get_fullname,
    get_function_body,
    get_function_call_args,
    get_function_def_args,
    is_call_to,
    lambda_in_rhs,
    remove_call_brackets,
)
from rattr.plugins import plugins


class FunctionAnalyser(NodeVisitor):
    """Walk a function's AST to determine the accessed attributes."""

    def __init__(self, _ast: ast.AST, context: Context) -> None:
        """Set configuration and initialise IR."""
        if not isinstance(_ast, AnyFunctionDef.__args__):
            raise TypeError("FunctionAnalyser expects `_ast` to be a function")

        self._ast: AnyFunctionDef = _ast

        self.func_ir: FunctionIR = {
            "sets": set(),
            "gets": set(),
            "dels": set(),
            "calls": set(),
        }

        # NOTE Managed by `new_context` contextmanager -- do not manually set
        self.context: Context = context

    def analyse(self) -> FunctionIR:
        """Entry point, return the results of analysis."""
        with new_context(self):
            self.context.push_arguments_to_context(self._ast.args)

            for stmt in get_function_body(self._ast):
                self.visit(stmt)

        return self.func_ir

    def get_and_verify_name(
        self, node: Nameable, ctx: ast.expr_context
    ) -> Tuple[str, str]:
        """Return the name, also verify validity."""
        base, full = get_basename_fullname_pair(node, safe=True)

        is_undeclared = base not in self.context
        is_assignment = isinstance(ctx, ast.Store)
        is_local = base.startswith(LOCAL_VALUE_PREFIX)

        if is_undeclared and not is_assignment and not is_local:
            error.warning(f"'{base}' potentially undefined", node)

        return base, full

    def update_results(self, symbol: Symbol, ctx: ast.expr_context) -> None:
        """Add the given name to the result.

        To be called on access -- i.e. ast.Name, etc.

        """
        if not isinstance(symbol, Symbol):
            raise TypeError()

        if isinstance(ctx, ast.Store):
            self.func_ir["sets"].add(symbol)

        if isinstance(ctx, ast.Load):
            self.func_ir["gets"].add(symbol)

        if isinstance(ctx, ast.Del):
            self.func_ir["dels"].add(symbol)

    # ----------------------------------------------------------------------- #
    # Result alterors: variables, call expressions, and subscripting
    # ----------------------------------------------------------------------- #

    def visit_Name(self, node: ast.Name) -> None:
        """Visit ast.Name(id: str, ctx: ast.expr_context)."""
        basename, fullname = self.get_and_verify_name(node, node.ctx)

        self.update_results(Name(fullname, basename), node.ctx)

    def visit_compound_nameable(self, node: CompoundStrictlyNameable) -> None:
        """Helper method for special nameable nodes.

        Visit ast.Starred(value, ctx).
        Visit ast.Attribute(value, attr: str, ctx: ast.expr_context).
        Visit ast.Subscript(value, slice, ctx).

        """
        basename, fullname = self.get_and_verify_name(node, node.ctx)

        # NOTE
        #   Visit the operands in a BinOp, etc.
        #   I.e.:
        #       In `(a + b).thing`, the the names `a` and `b` should also be
        #       visited
        #       In `a.thing`, the expr should be visted once as a whole
        #       (neither `a` nor `thing` should be visited directly)
        if not isinstance(node.value, StrictlyNameable.__args__):
            self.generic_visit(node.value)

        self.update_results(Name(fullname, basename), node.ctx)

    def visit_Starred(self, node: ast.Starred) -> None:
        self.visit_compound_nameable(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.visit_compound_nameable(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        self.visit_compound_nameable(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Visit ast.Call(func, args, keywords)."""
        _, fullname = self.get_and_verify_name(node, ast.Load())

        # Handle special builtins such as getattr, setattr, etc
        if self.handle_special_function(node):
            return

        # NOTE
        #   Add the call to the IR and manually visit the arguments,
        #   but not `node.func` as it will register an incorrect "gets"

        target = self.context.get_call_target(fullname, node)

        if not isinstance(target, Class):
            args = get_function_call_args(node)
        else:
            error.warning(f"'{target.name}' initialised but not stored", node)
            args = get_function_call_args(node, LOCAL_VALUE_PREFIX + target.name)

        # NOTE
        #   If this is a call to a method on an attribute, then it necessarily
        #   "gets" the attribute
        parts = remove_call_brackets(fullname).split(".")[:-1]
        for attr in list(accumulate(parts, lambda a, b: f"{a}.{b}"))[1:]:
            self.func_ir["gets"].add(Name(attr, parts[0]))

        self.func_ir["calls"].add(Call(fullname, *args, target))

        for arg in (*node.args, *node.keywords):
            self.visit(arg)

    # ----------------------------------------------------------------------- #
    # Result alterors: special functions
    # ----------------------------------------------------------------------- #

    def handle_special_function(self, node: ast.Call) -> bool:
        """Return `True` if handled."""
        if isinstance(node.func, ast.Name):
            name = remove_call_brackets(node.func.id)
        else:
            name = remove_call_brackets(get_fullname(node, safe=True))

        analyser = plugins.custom_function_handler.get(name, self.context.get_root())

        if analyser is None:
            return False

        ir = analyser.on_call(name, node, self.context)

        self.func_ir["sets"] = set.union(self.func_ir["sets"], ir["sets"])
        self.func_ir["gets"] = set.union(self.func_ir["gets"], ir["gets"])
        self.func_ir["dels"] = set.union(self.func_ir["dels"], ir["dels"])
        self.func_ir["calls"] = set.union(self.func_ir["calls"], ir["calls"])

        return True

    # ----------------------------------------------------------------------- #
    # Context alterors: assignments and deleteion
    # ----------------------------------------------------------------------- #

    def visit_LambdaAssign(self, node: AnyAssign, targets: List[ast.expr]) -> None:
        """Helper method for handling non-anonymous lambdas."""
        target = targets[0]

        if not assignment_is_one_to_one(node):
            error.fatal("lambda assignment must be one-to-one", node)

        error.error("unable to unbind lambdas defined in functions", node)

        name = get_fullname(target)
        func = Func(name, *get_function_def_args(node.value))

        self.context.add(func)

    def visit_ClassAssign(self, node: AnyAssign, targets: List[ast.expr]) -> None:
        """Helper method for assignments where RHS is a new class instance."""
        target = targets[0]

        if not assignment_is_one_to_one(node):
            error.fatal("class assignment must be one-to-one", node)

        # Create call to class initialiser
        lhs_basename, lhs_name = get_basename_fullname_pair(target)
        class_name = get_fullname(node.value)

        init_args = get_function_call_args(node.value, lhs_name)
        init_body = self.context.get_call_target(class_name, node)

        self.func_ir["calls"].add(Call(class_name, *init_args, init_body))

        # Create set to LHS
        self.func_ir["sets"].add(Name(lhs_name, lhs_basename))

        # Register assignments
        for target in targets:
            self.context.add_identifiers_to_context(target)

        # Visit call arguments
        for arg in (*node.value.args, *node.value.keywords):
            self.visit(arg)

    def visit_AnyAssign(self, node: AnyAssign) -> None:
        """Helper method for assignments.

        Visit ast.Assign(targets, value, type_comment)\\
        Visit ast.AnnAssign(target, annotation, value, simple)\\
        Visit ast.AugAssign(target, op, value)

        """
        targets = get_assignment_targets(node)

        # NOTE Handle special case, non-anonymous lambda
        if lambda_in_rhs(node):
            self.visit_LambdaAssign(node, targets)
            return

        # NOTE Handle special case, rhs is class
        if class_in_rhs(node, self.context):
            self.visit_ClassAssign(node, targets)
            return

        for target in targets:
            self.context.add_identifiers_to_context(target)

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit_AnyAssign(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit_AnyAssign(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit_AnyAssign(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        """Visit ast.Delete(targets)."""
        for target in node.targets:
            self.context.del_identifiers_from_context(target)

        return self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        """Visit ast.For(target, iter, body, orelse, type_comment)."""
        self.context.add_identifiers_to_context(node.target)

        return self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        """Visit ast.AsyncFor(target, iter, body, orelse)."""
        self.context.add_identifiers_to_context(node.target)

        return self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        """Visit ast.With(items, body, type_comment)."""
        for item in node.items:
            if not item.optional_vars:
                continue
            self.context.add_identifiers_to_context(item.optional_vars)

        return self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        """Visit ast.class AsyncWith(items, body)."""
        for item in node.items:
            if not item.optional_vars:
                continue
            self.context.add_identifiers_to_context(item.optional_vars)

        return self.generic_visit(node)

    # ----------------------------------------------------------------------- #
    # Context creators: function, class definitions, etc
    # ----------------------------------------------------------------------- #

    def visit_AnyFunctionDef(self, node: AnyFunctionDef) -> None:
        """Helper method for visiting nested function definitions.

        Visit ast.FunctionDef(name, args, body, decorator_list, returns)\\
        Visit ast.AsyncFunctionDef(name, args, body, decorator_list, returns)\\
        Visit ast.Lambda(args, body)

        NOTE:
            visit_Lambda(lambda) and thus visit_AnyFunctionDef(lambda), are
            only reached when the lambda is an anonymous function.

        """
        args = get_function_def_args(node)

        if not isinstance(node, ast.Lambda):
            error.error("unable to unbind nested functions", node)
        else:
            error.error("unable to unbind anonymous lambdas", node)

        if isinstance(node, ast.FunctionDef):
            self.context.add(Func(node.name, *args))
        if isinstance(node, ast.AsyncFunctionDef):
            self.context.add(Func(node.name, *args, is_async=True))

        # TODO Allow nested -- FunctionAnalyser on name "outer.inner"
        with new_context(self):
            self.context.push_arguments_to_context(node.args)

            for stmt in get_function_body(node):
                self.visit(stmt)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.visit_AnyFunctionDef(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_AnyFunctionDef(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.visit_AnyFunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return error.error("nested classes unsupported", node)

    # ----------------------------------------------------------------------- #
    # Context creators: comprehensions and generators
    # ----------------------------------------------------------------------- #

    def visit_comprehension(self, node: ast.comprehension) -> None:
        """Visit ast.comprehension(target, iter, ifs, is_async)."""
        # Add target to context
        self.context.add_identifiers_to_context(node.target)

        # If iter isn't defined by another target, visit it
        basename = get_basename(node.iter, safe=True)
        if not self.context.declares(basename):
            self.generic_visit(node.iter)

        for if_stmt in node.ifs:
            self.generic_visit(if_stmt)

    def visit_GenericComp(
        self, generators: List[ast.comprehension], exprs: List[ast.expr]
    ) -> None:
        """Helper method visit an arbitrary comprehension.

        Visit ast.ListComp(elt: ast.expr, generators: ast.comprehension).
        Visit ast.SetComp(elt, generators).
        Visit ast.GeneratorExp(elt, generators).
        Visit ast.DictComp(key, value, generators).

        NOTE:
            Ordinarily, the attributes are visited in order:
                elt / key, value
                generators
            However, as the generators create a local scope, we wish to visit
            them first.

        """
        with new_context(self):
            for comp in generators:
                self.visit_comprehension(comp)

            for expr in exprs:
                self.generic_visit(expr)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self.visit_GenericComp(node.generators, [node.elt])

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self.visit_GenericComp(node.generators, [node.elt])

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self.visit_GenericComp(node.generators, [node.elt])

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self.visit_GenericComp(node.generators, [node.key, node.value])

    # ----------------------------------------------------------------------- #
    # Special cases
    # ----------------------------------------------------------------------- #

    def visit_ReturnValue(self, node: Optional[ast.expr]) -> bool:
        """Helper method to handle a return value / tuple elt.

        Returns True if the return value has been fully handled.

        """
        if node is None:
            return True

        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            for elt in node.elts:
                handled = self.visit_ReturnValue(elt)

                if not handled:
                    self.visit(elt)

            return True

        if isinstance(node, ast.Dict):
            for elt in (*node.keys, *node.values):
                handled = self.visit_ReturnValue(elt)

                if not handled:
                    self.visit(elt)

            return True

        if isinstance(node, ast.Call):
            # NOTE
            #   get_basename_fullname_pair on getattr, etc. produces a name
            #   incompatible with Context::get_call_target
            if any(is_call_to(f, node) for f in PYTHON_ATTR_BUILTINS):
                return False

            target = self.context.get_call_target(
                get_fullname(node, True), node, warn=False
            )

            if not isinstance(target, Class):
                return False

            # Create call to class initialiser
            class_name = get_fullname(node)

            init_args = get_function_call_args(node, "@ReturnValue")
            init_body = self.context.get_call_target(class_name, node)

            self.func_ir["calls"].add(Call(class_name, *init_args, init_body))

            # Visit call arguments
            for arg in (*node.args, *node.keywords):
                self.visit(arg)

            return True

        return False

    def visit_Return(self, node: ast.Return) -> None:
        """Visit ast.Return(value)."""
        handled = self.visit_ReturnValue(node.value)

        if not handled:
            self.visit(node.value)

    # ----------------------------------------------------------------------- #
    # THE FORBIDEN ZONE: A zone... that is, yes... FORBIDDEN to you.
    # ----------------------------------------------------------------------- #

    def visit_Global(self, node: ast.Global) -> None:
        return error.fatal("do not use global keyword", node)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        return error.fatal("do not use nonlocal keyword", node)

    def visit_Import(self, node: ast.Import) -> None:
        return error.fatal("imports must be at the top level", node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        return error.fatal("imports must be at the top level", node)
