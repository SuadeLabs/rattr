"""CustomFunctionAnalyser for Python's collections."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from rattr.analyser.base import CustomFunctionAnalyser
from rattr.analyser.types import FunctionIr
from rattr.ast.util import fullname_of
from rattr.models.symbol import Call, CallArguments

if TYPE_CHECKING:
    from rattr.models.context import Context


def as_ast_lambda(expr: ast.expr) -> ast.Lambda:
    return ast.Lambda(
        args=ast.arguments(
            posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
        ),
        body=expr,
    )


class DefaultDictAnalyser(CustomFunctionAnalyser):
    @property
    def name(self) -> str:
        return "defaultdict"

    @property
    def qualified_name(self) -> str:
        return "collections.defaultdict"

    def on_def(
        self,
        name: str,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        ctx: Context,
    ) -> FunctionIr:
        return super().on_def(name, node, ctx)

    def on_call(self, name: str, node: ast.Call, ctx: Context) -> FunctionIr:
        # HACK Avoid circular import
        from rattr.analyser.function import FunctionAnalyser

        if len(node.args) == 0:
            return super().on_call(name, node, ctx)

        default_factory = node.args[0]

        # Three cases:
        #   1. A named callable         ->  Add call to name
        #   2. A lambda                 ->  Visit lambda
        #   3. Non-lambda expression    ->  Visit expression as dummy lambda

        if isinstance(default_factory, (ast.Name, ast.Attribute)):
            name = fullname_of(default_factory)
            target = ctx.get_call_target(name, culprit=node)
            results = FunctionIr.new(
                calls={
                    Call(
                        name=name,
                        args=CallArguments(),
                        target=target,
                        token=default_factory,
                    ),
                }
            )
        elif isinstance(default_factory, ast.Lambda):
            results = FunctionAnalyser(default_factory, ctx).analyse()
        else:
            results = FunctionAnalyser(as_ast_lambda(default_factory), ctx).analyse()

        return results
