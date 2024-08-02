"""Rattr function analyser."""
from __future__ import annotations

import ast
from itertools import accumulate
from typing import TYPE_CHECKING

from rattr import error
from rattr.analyser.base import NodeVisitor
from rattr.analyser.util import (
    assignment_is_one_to_one,
    class_in_rhs,
    get_assignment_targets,
    get_function_body,
    is_call_to,
    lambda_in_rhs,
    namedtuple_in_rhs,
)
from rattr.ast.types import AstFunctionDefOrLambda, AstNodeWithName
from rattr.ast.util import (
    fullname_of,
    namedtuple_init_signature_from_declaration,
    names_of,
)
from rattr.config import Config
from rattr.models.context import Context, new_context
from rattr.models.ir import FunctionIr
from rattr.models.symbol import (
    PYTHON_ATTR_ACCESS_BUILTINS,
    Call,
    CallInterface,
    Class,
    Func,
    Name,
)
from rattr.models.symbol.util import without_call_brackets
from rattr.plugins import plugins

if TYPE_CHECKING:
    from rattr.models.plugins import CustomFunctionAnalyser


def custom_analyser_for_target(
    node: ast.Call,
    context: Context,
) -> CustomFunctionAnalyser | None:
    target_name = without_call_brackets(
        fullname_of(
            node,
            unravel_attr_access_calls=False,
            safe=True,
        )
    )
    target_symbol = context.get_call_target(target_name, node, warn=False)

    return plugins.get_analyser(target_symbol, modulename=context.modulename)


class FunctionAnalyser(NodeVisitor):
    """Walk a function's AST to determine the accessed attributes."""

    def __init__(self, ast_function: ast.AST, context: Context) -> None:
        """Set configuration and initialise IR."""
        if not isinstance(ast_function, AstFunctionDefOrLambda):
            raise TypeError("FunctionAnalyser expects `_ast` to be a function")

        self.ast: ast.Lambda | ast.FunctionDef | ast.AsyncFunctionDef = ast_function

        self.func_ir: FunctionIr = {
            "gets": set(),
            "sets": set(),
            "dels": set(),
            "calls": set(),
        }

        self.context: Context = context
        """Managed by `new_context`."""

    def analyse(self) -> FunctionIr:
        """Entry point, return the results of analysis."""
        with new_context(self):
            self.context.add_arguments_to_context(self.ast.args, token=self.ast)

            for stmt in get_function_body(self.ast):
                self.visit(stmt)

        return self.func_ir

    def get_and_verify_name(
        self,
        node: ast.expr,
        ctx: ast.expr_context,
    ) -> tuple[str, str]:
        """Return the name, also verify validity."""
        config = Config()

        base, full = names_of(node, safe=True)

        is_undeclared = base not in self.context
        is_assignment = isinstance(ctx, ast.Store)
        is_literal = base.startswith(config.LITERAL_VALUE_PREFIX)

        if is_undeclared and not is_assignment and not is_literal:
            error.warning(f"{base!r} potentially undefined", node)

        return base, full

    def update_results(self, symbol: Name, ctx: ast.expr_context) -> None:
        """Add the given name to the result."""
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
        self.update_results(Name(fullname, basename, token=node), node.ctx)

    def visit_compound_name(
        self,
        node: ast.Attribute | ast.Starred | ast.Subscript,
    ) -> None:
        """Helper method for special nameable nodes.

        Visit ast.Starred(value, ctx).
        Visit ast.Attribute(value, attr: str, ctx: ast.expr_context).
        Visit ast.Subscript(value, slice, ctx).

        """
        basename, fullname = self.get_and_verify_name(node, node.ctx)

        # Visit the operands in a BinOp such as `(a + b).thing`, etc.
        if not isinstance(node.value, AstNodeWithName):
            self.visit(node.value)

        self.update_results(Name(fullname, basename, token=node), node.ctx)

    def visit_Starred(self, node: ast.Starred) -> None:
        self.visit_compound_name(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.visit_compound_name(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        self.visit_compound_name(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Visit ast.Call(func, args, keywords)."""
        config = Config()

        if (analyser := custom_analyser_for_target(node, self.context)) is not None:
            return self.visit_call_to_target_with_custom_analyser(node, analyser)

        _, fullname = self.get_and_verify_name(node, ast.Load())
        target = self.context.get_call_target(fullname, node, warn=True)

        # NOTE
        # Add the call to the IR and manually visit the arguments, but not `node.func`
        # as it will register an incorrect "gets"

        if isinstance(target, Class):
            error.warning(f"{target.name!r} initialised but not stored", node)
            self_name = config.LITERAL_VALUE_PREFIX + target.name
        else:
            self_name = None

        # TODO Refactor
        # On a call to `cls.member.method()` then it must get `class.member`
        parts = without_call_brackets(fullname).split(".")[:-1]
        for attr in list(accumulate(parts, lambda a, b: f"{a}.{b}"))[1:]:
            self.func_ir["gets"].add(Name(attr, parts[0], token=node))

        call = Call.from_call(fullname, call=node, target=target, self=self_name)
        self.func_ir["calls"].add(call)

        for arg in (*node.args, *node.keywords):
            self.visit(arg)

    def visit_call_to_target_with_custom_analyser(
        self,
        node: ast.Call,
        custom_analyser: CustomFunctionAnalyser,
    ) -> None:
        target_name = without_call_brackets(
            fullname_of(
                node,
                unravel_attr_access_calls=False,
                safe=True,
            )
        )
        target_call_ir = custom_analyser.on_call(target_name, node, self.context)

        self.func_ir["gets"] |= target_call_ir["gets"]
        self.func_ir["sets"] |= target_call_ir["sets"]
        self.func_ir["dels"] |= target_call_ir["dels"]
        self.func_ir["calls"] |= target_call_ir["calls"]

    # ----------------------------------------------------------------------- #
    # Context alterors: assignments and deleteion
    # ----------------------------------------------------------------------- #

    def visit_LambdaAssign(
        self,
        node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
        targets: list[ast.expr],
    ) -> None:
        """Helper method for handling non-anonymous lambdas."""
        target = targets[0]

        if not assignment_is_one_to_one(node):
            error.fatal("lambda assignment must be one-to-one", node)

        error.error("unable to unbind lambdas defined in functions", node)

        name = fullname_of(target)

        if not isinstance(node.value, ast.Lambda):
            error.fatal("unable to find lambda in rhs")  # never

        func = Func(
            name=name,
            token=node,
            interface=CallInterface.from_fn_def(node.value),
        )
        self.context.add(func)

    def visit_NamedTupleAssign(
        self,
        node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
        targets: list[ast.expr],
    ) -> None:
        """Helper method for handling non-anonymous lambdas."""
        target = targets[0]

        if not assignment_is_one_to_one(node):
            error.fatal("namedtuple assignment must be one-to-one", culprit=node)

        name = fullname_of(target)
        try:
            arguments = namedtuple_init_signature_from_declaration(node)
        except ValueError as exc:
            return error.error(str(exc.args[0]), culprit=node)

        cls = Class(name=name, token=node, interface=CallInterface(args=arguments))
        self.context.add(cls)

    def visit_ClassAssign(
        self,
        node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
        targets: list[ast.expr],
    ) -> None:
        """Helper method for assignments where RHS is a new class instance."""
        target = targets[0]

        if not assignment_is_one_to_one(node):
            error.fatal("class assignment must be one-to-one", node)

        # Create call to class initialiser
        lhs_basename, lhs_name = names_of(target)

        if not isinstance(node.value, ast.Call):
            raise RuntimeError("class assignment call is missing")  # never

        class_name = fullname_of(node.value)
        init_body = self.context.get_call_target(class_name, node)

        call = Call.from_call(
            class_name,
            call=node.value,
            target=init_body,
            self=lhs_name,
        )
        self.func_ir["calls"].add(call)

        # Create set to LHS
        self.func_ir["sets"].add(Name(lhs_name, lhs_basename, token=node))

        # Register assignments
        for target in targets:
            self.context.add_identifiers_to_context(target)

        # Visit call arguments
        for arg in (*node.value.args, *node.value.keywords):
            self.visit(arg)

    def visit_AnyAssign(
        self,
        node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
    ) -> None:
        """Helper method for assignments.

        Visit ast.Assign(targets, value, type_comment)\\
        Visit ast.AnnAssign(target, annotation, value, simple)\\
        Visit ast.AugAssign(target, op, value)

        """
        targets = get_assignment_targets(node)

        if lambda_in_rhs(node):
            self.visit_LambdaAssign(node, targets)
            return

        if namedtuple_in_rhs(node):
            self.visit_NamedTupleAssign(node, targets)
            return

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

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.func_ir["sets"].add(Name(*names_of(node.target), token=node))

        if lambda_in_rhs(node):
            self.visit(node.value)

        self.visit_AnyAssign(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        """Visit ast.Delete(targets)."""
        for target in node.targets:
            self.context.remove_identifiers_from_context(target)

        self.generic_visit(node)

    def _visit_for_loop(self, node: ast.For | ast.AsyncFor) -> None:
        self.context.add_identifiers_to_context(node.target)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._visit_for_loop(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._visit_for_loop(node)

    def visit_With(self, node: ast.With) -> None:
        """Visit ast.With(items, body, type_comment)."""
        for item in node.items:
            if not item.optional_vars:
                continue
            self.context.add_identifiers_to_context(item.optional_vars)

        self.generic_visit(node)

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

    def visit_AnyFunctionDef(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
    ) -> None:
        """Helper method for visiting nested function definitions.

        Visit ast.FunctionDef(name, args, body, decorator_list, returns)\\
        Visit ast.AsyncFunctionDef(name, args, body, decorator_list, returns)\\
        Visit ast.Lambda(args, body)

        NOTE:
            visit_Lambda(lambda) and thus visit_AnyFunctionDef(lambda), are
            only reached when the lambda is an anonymous function.

        """
        if not isinstance(node, ast.Lambda):
            error.error("unable to unbind nested functions", node)
        else:
            error.error("unable to unbind anonymous lambdas", node)

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.context.add(Func.from_fn_def(node))

        # TODO Allow nested -- FunctionAnalyser on name "outer.inner"
        with new_context(self):
            self.context.add_arguments_to_context(node.args, token=node)

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

    # -------------------------------------------------------------------------------- #
    # Comprehensions and generators
    # -------------------------------------------------------------------------------- #

    def _visit_any_comprehension_or_generator_expr(
        self,
        node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
        names: list[ast.expr],
    ) -> None:
        with new_context(self):
            # Visit the comprehensions first as they may define some of the names in
            # `names`, thus avoiding erroneous "potentially undefined" warnings.
            for comprehension in node.generators:
                self.visit(comprehension)

            for name in names:
                self.visit(name)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        # Add the target (i.e. in `for x in xs` then `x` is the target) to the context
        # first to avoid "'x' potentially undefined".
        self.context.add_identifiers_to_context(node.target)

        for expr in (node.target, node.iter, *node.ifs):
            self.visit(expr)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_any_comprehension_or_generator_expr(node, [node.elt])

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_any_comprehension_or_generator_expr(node, [node.elt])

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_any_comprehension_or_generator_expr(node, [node.key, node.value])

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_any_comprehension_or_generator_expr(node, [node.elt])

    # ----------------------------------------------------------------------- #
    # Special cases
    # ----------------------------------------------------------------------- #

    def visit_ReturnValue(self, node: ast.expr | None) -> bool:
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

                if not handled and elt is not None:
                    self.visit(elt)

            return True

        if isinstance(node, ast.Call):
            # NOTE
            #   get_basename_fullname_pair on getattr, etc. produces a name
            #   incompatible with Context::get_call_target
            if any(is_call_to(f, node) for f in PYTHON_ATTR_ACCESS_BUILTINS):
                return False

            target = self.context.get_call_target(
                fullname_of(node, safe=True),
                node,
                warn=False,
            )

            if not isinstance(target, Class):
                return False

            # Create call to class initialiser
            class_name = fullname_of(node)
            init_body = self.context.get_call_target(class_name, node)
            call = Call.from_call(
                class_name,
                call=node,
                target=init_body,
                self="@ReturnValue",
            )
            self.func_ir["calls"].add(call)

            # Visit call arguments
            for arg in (*node.args, *node.keywords):
                self.visit(arg)

            return True

        return False

    def visit_Return(self, node: ast.Return) -> None:
        """Visit ast.Return(value)."""
        handled = self.visit_ReturnValue(node.value)

        if not handled and node.value is not None:
            self.visit(node.value)

    # ----------------------------------------------------------------------- #
    # THE FORBIDDEN ZONE: A zone... that is, yes... FORBIDDEN to you.
    # ----------------------------------------------------------------------- #

    def visit_Global(self, node: ast.Global) -> None:
        return error.fatal("do not use global keyword", node)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        return error.fatal("do not use nonlocal keyword", node)

    def visit_Import(self, node: ast.Import) -> None:
        return error.fatal("imports must be at the top level", node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        return error.fatal("imports must be at the top level", node)
