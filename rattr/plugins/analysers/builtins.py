"""CustomFunctionAnalyser for Python's builtin functions."""

import ast

from rattr.analyser.base import CustomFunctionAnalyser
from rattr.analyser.context import Context
from rattr.analyser.types import FuncOrAsyncFunc, FunctionIR
from rattr.analyser.util import get_dynamic_name, get_fullname


class GetattrAnalyser(CustomFunctionAnalyser):
    @property
    def name(self) -> str:
        return "getattr"

    @property
    def qualified_name(self) -> str:
        return "getattr"

    def on_def(self, name: str, node: FuncOrAsyncFunc, ctx: Context) -> FunctionIR:
        return super().on_def(name, node, ctx)

    def on_call(self, name: str, node: ast.Call, ctx: Context) -> FunctionIR:
        return {
            "sets": set(),
            "gets": {
                get_dynamic_name(name, node, "{first}.{second}"),
            },
            "dels": set(),
            "calls": set(),
        }


class SetattrAnalyser(CustomFunctionAnalyser):
    @property
    def name(self) -> str:
        return "setattr"

    @property
    def qualified_name(self) -> str:
        return "setattr"

    def on_def(self, name: str, node: FuncOrAsyncFunc, ctx: Context) -> FunctionIR:
        return super().on_def(name, node, ctx)

    def on_call(self, name: str, node: ast.Call, ctx: Context) -> FunctionIR:
        return {
            "sets": {
                get_dynamic_name(name, node, "{first}.{second}"),
            },
            "gets": set(),
            "dels": set(),
            "calls": set(),
        }


class HasattrAnalyser(CustomFunctionAnalyser):
    @property
    def name(self) -> str:
        return "hasattr"

    @property
    def qualified_name(self) -> str:
        return "hasattr"

    def on_def(self, name: str, node: FuncOrAsyncFunc, ctx: Context) -> FunctionIR:
        return super().on_def(name, node, ctx)

    def on_call(self, name: str, node: ast.Call, ctx: Context) -> FunctionIR:
        return {
            "sets": set(),
            "gets": {
                get_dynamic_name(name, node, "{first}.{second}"),
            },
            "dels": set(),
            "calls": set(),
        }


class DelattrAnalyser(CustomFunctionAnalyser):
    @property
    def name(self) -> str:
        return "delattr"

    @property
    def qualified_name(self) -> str:
        return "delattr"

    def on_def(self, name: str, node: FuncOrAsyncFunc, ctx: Context) -> FunctionIR:
        return super().on_def(name, node, ctx)

    def on_call(self, name: str, node: ast.Call, ctx: Context) -> FunctionIR:
        return {
            "sets": set(),
            "gets": set(),
            "dels": {
                get_dynamic_name(name, node, "{first}.{second}"),
            },
            "calls": set(),
        }


class SortedAnalyser(CustomFunctionAnalyser):
    @property
    def name(self) -> str:
        return "sorted"

    @property
    def qualified_name(self) -> str:
        return "sorted"

    def on_def(self, name: str, node: FuncOrAsyncFunc, ctx: Context) -> FunctionIR:
        return super().on_def(name, node, ctx)

    def on_call(self, name: str, node: ast.Call, ctx: Context) -> FunctionIR:
        # HACK Avoid circular import
        from rattr.analyser.context.symbol import Name
        from rattr.analyser.function import FunctionAnalyser
        from rattr.analyser.ir_dag import partially_unbind

        if len(node.args) == 0:
            return super().on_call(name, node, ctx)

        fn_analyser = FunctionAnalyser(ast.FunctionDef(), ctx)

        # The first arg may be a get/call within the context
        fn_analyser.visit(node.args[0])

        # If there is a key, it should be visited
        key = None

        for kw in node.keywords:
            if kw.arg == "key":
                key = kw

        if key is None:
            return fn_analyser.func_ir

        if isinstance(key.value, ast.Lambda):
            # NOTE The lambda in `sorted` expects exactly one argument
            if len(key.value.args.args) != 1:
                raise SyntaxError

            # HACK
            #   Visit the lambda in a different FunctionAnalyser s.t. the
            #   key-argument-name can be unbound without interfering with the
            #   results from visiting the sorting target

            iterator = key.value.args.args[0].arg
            iterable = get_fullname(node.args[0], safe=True)

            lambda_ctx = Context(ctx)
            lambda_ctx.add(Name(iterator), is_argument=True)

            lambda_analyser = FunctionAnalyser(ast.FunctionDef(), lambda_ctx)
            lambda_analyser.visit(key.value.body)

            # Substitute
            lambda_analyser.func_ir = partially_unbind(
                lambda_analyser.func_ir, {iterator: iterable}
            )

            # Union
            fn_analyser.func_ir["gets"] = fn_analyser.func_ir["gets"].union(
                lambda_analyser.func_ir["gets"]
            )
            fn_analyser.func_ir["sets"] = fn_analyser.func_ir["sets"].union(
                lambda_analyser.func_ir["sets"]
            )
            fn_analyser.func_ir["dels"] = fn_analyser.func_ir["dels"].union(
                lambda_analyser.func_ir["dels"]
            )
            fn_analyser.func_ir["calls"] = fn_analyser.func_ir["calls"].union(
                lambda_analyser.func_ir["calls"]
            )
        else:
            fn_analyser.visit(key.value)

        return fn_analyser.func_ir
