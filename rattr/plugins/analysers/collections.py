"""CustomFunctionAnalyser for Python's collections."""

import ast

from rattr.analyser.base import CustomFunctionAnalyser
from rattr.analyser.context import Context
from rattr.analyser.types import FuncOrAsyncFunc, FunctionIR


class DefaultDictAnalyser(CustomFunctionAnalyser):
    @property
    def name(self) -> str:
        return "defaultdict"

    @property
    def qualified_name(self) -> str:
        return "collections.defaultdict"

    def on_def(self, name: str, node: FuncOrAsyncFunc, ctx: Context) -> FunctionIR:
        return super().on_def(name, node, ctx)

    def on_call(self, name: str, node: ast.Call, ctx: Context) -> FunctionIR:
        # HACK Avoid circular import
        from rattr.analyser.function import FunctionAnalyser

        if len(node.args) == 0:
            return super().on_call(name, node, ctx)

        default_factory = node.args[0]

        # Three cases:
        #   1. A named callable         ->  Add call to name
        #   2. A lambda                 ->  Fold-in results of body
        #   3. Non-lambda expression    ->  Visit

        fn_analyser = FunctionAnalyser(ast.FunctionDef(), ctx)

        if isinstance(default_factory, (ast.Name, ast.Attribute)):
            target = ast.Call(
                func=default_factory,
                args=[],
                keywords=[],
            )

            # Populate ast.AST fields
            target._fields = tuple()
            target.lineno = default_factory.lineno
            target.col_offset = default_factory.col_offset
        elif isinstance(default_factory, ast.Lambda):
            target = default_factory.body
        else:
            target = default_factory

        fn_analyser.visit(target)

        return fn_analyser.func_ir
