"""CustomFunctionAnalyser for Python's builtin functions."""

import ast

from ratter.analyser.base import CustomFunctionAnalyser
from ratter.analyser.context import Context
from ratter.analyser.types import FuncOrAsyncFunc, FunctionIR
from ratter.analyser.util import get_dynamic_name


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
