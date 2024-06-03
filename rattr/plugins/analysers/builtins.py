"""CustomFunctionAnalyser for Python's builtin functions."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, NamedTuple

from rattr.analyser.base import CustomFunctionAnalyser
from rattr.analyser.util import get_dynamic_name
from rattr.ast.util import fullname_of
from rattr.models.context import Context
from rattr.models.symbol import Name
from rattr.results import unbind_ir_with_call_swaps

if TYPE_CHECKING:
    from collections.abc import Iterator

    from rattr.ast.types import Identifier
    from rattr.models.ir import FunctionIr


class AccessedAttributes(NamedTuple):
    full: Name
    lhs_names: list[Name]


def iter_lhs_names(target: Name) -> Iterator[Identifier]:
    parts = target.name.split(".")

    if parts == [target]:
        yield target
        return

    for end_offset in range(1, len(parts)):
        yield ".".join(parts[:-end_offset])


def accessed_attributes(name: str, node: ast.Call) -> AccessedAttributes:
    return AccessedAttributes(
        full=(full := get_dynamic_name(name, node, "{first}.{second}")),
        lhs_names=[Name(name) for name in iter_lhs_names(full)],
    )


class GetattrAnalyser(CustomFunctionAnalyser):
    @property
    def name(self) -> str:
        return "getattr"

    @property
    def qualified_name(self) -> str:
        return "getattr"

    def on_def(
        self,
        name: str,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        ctx: Context,
    ) -> FunctionIr:
        return super().on_def(name, node, ctx)

    def on_call(self, name: str, node: ast.Call, ctx: Context) -> FunctionIr:
        full, lhs_names = accessed_attributes(name, node)
        return {
            "gets": {full, *lhs_names},
            "sets": set(),
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

    def on_def(
        self,
        name: str,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        ctx: Context,
    ) -> FunctionIr:
        return super().on_def(name, node, ctx)

    def on_call(self, name: str, node: ast.Call, ctx: Context) -> FunctionIr:
        full, lhs_names = accessed_attributes(name, node)
        return {
            "gets": {*lhs_names},
            "sets": {full},
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

    def on_def(
        self,
        name: str,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        ctx: Context,
    ) -> FunctionIr:
        return super().on_def(name, node, ctx)

    def on_call(self, name: str, node: ast.Call, ctx: Context) -> FunctionIr:
        full, lhs_names = accessed_attributes(name, node)
        return {
            "gets": {full, *lhs_names},
            "sets": set(),
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

    def on_def(
        self,
        name: str,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        ctx: Context,
    ) -> FunctionIr:
        return super().on_def(name, node, ctx)

    def on_call(self, name: str, node: ast.Call, ctx: Context) -> FunctionIr:
        full, lhs_names = accessed_attributes(name, node)
        return {
            "gets": {*lhs_names},
            "sets": set(),
            "dels": {full},
            "calls": set(),
        }


class SortedAnalyser(CustomFunctionAnalyser):
    @property
    def name(self) -> str:
        return "sorted"

    @property
    def qualified_name(self) -> str:
        return "sorted"

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
            iterable = fullname_of(node.args[0], safe=True)

            lambda_ctx = Context(ctx)
            lambda_ctx.add(Name(iterator, token=node), is_argument=True)

            lambda_analyser = FunctionAnalyser(ast.FunctionDef(), lambda_ctx)
            lambda_analyser.visit(key.value.body)

            # Substitute
            lambda_analyser.func_ir = unbind_ir_with_call_swaps(
                lambda_analyser.func_ir,
                {iterator: iterable},
            )

            fn_analyser.func_ir["gets"] |= lambda_analyser.func_ir["gets"]
            fn_analyser.func_ir["sets"] |= lambda_analyser.func_ir["sets"]
            fn_analyser.func_ir["dels"] |= lambda_analyser.func_ir["dels"]
            fn_analyser.func_ir["calls"] |= lambda_analyser.func_ir["calls"]

        else:
            fn_analyser.visit(key.value)

        return fn_analyser.func_ir
