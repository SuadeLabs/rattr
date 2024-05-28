"""Assert that there are no assignment to names that identify imports."""
from __future__ import annotations

import ast
from contextlib import contextmanager
from typing import TYPE_CHECKING

from rattr.analyser.base import Assertor
from rattr.analyser.util import has_annotation
from rattr.ast.util import fullname_of, unravel_names
from rattr.models.context import Context
from rattr.models.symbol import CallInterface, Import

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from rattr.ast.types import Identifier


def lhs_names(
    lhs: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
) -> list[str]:
    """Return the names in the lhs of the given assignment."""
    if hasattr(lhs, "targets"):
        targets = lhs.targets
    else:
        targets = [lhs.target]

    return [
        name
        for target in targets
        for name in unravel_names(target, _get_name=fullname_of)
    ]


def imports_in_node_lhs_names(
    node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
    *,
    context: Context,
) -> list[Import]:
    return imports_in_names(lhs_names(node), context=context)


def imports_in_names(
    names: Iterable[Identifier],
    *,
    context: Context,
) -> list[Import]:
    return [
        symbol
        for name in names
        if (symbol := context.get(name)) is not None
        if isinstance(symbol, Import)
    ]


class ImportClobberingAssertor(Assertor):
    def __init__(self, is_strict: bool = True) -> None:
        super().__init__(is_strict=is_strict)
        self.class_stack: list[str] = []

    @contextmanager
    def enter_class_name(self, name: str) -> Generator[None, None, None]:
        self.class_stack.append(name)
        yield
        self.class_stack.pop()

    def __clobbered(self, name: str, node: ast.AST) -> None:
        self.failed(f"redefinition of imported name {name!r}", culprit=node)

    def __deleted(self, name: str, node: ast.AST) -> None:
        self.failed(f"attempt to delete imported name {name!r}", culprit=node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for import_ in imports_in_node_lhs_names(node, context=self.context):
            self.__clobbered(import_.name, node)

        return super().generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        for import_ in imports_in_node_lhs_names(node, context=self.context):
            self.__clobbered(import_.name, node)

        return super().generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        for import_ in imports_in_node_lhs_names(node, context=self.context):
            self.__clobbered(import_.name, node)

        return super().generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        for import_ in imports_in_node_lhs_names(node, context=self.context):
            self.__deleted(import_.name, node)

        return super().generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if has_annotation("rattr_ignore", node):
            return

        if has_annotation("rattr_results", node):
            return

        is_in_method = self.class_stack != []

        if not is_in_method and isinstance(self.context.get(node.name), Import):
            return self.__clobbered(node.name, node)

        self.check_arguments(node)

        return super().generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return self.visit_FunctionDef(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.check_arguments(node)
        return super().generic_visit(node)

    def check_arguments(
        self,
        node: ast.Lambda | ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        interface = CallInterface.from_fn_def(node)
        names = {a for a in interface.all if a is not None}

        for import_ in imports_in_names(names, context=self.context):
            self.__clobbered(import_.name, node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if has_annotation("rattr_ignore", node):
            return

        if has_annotation("rattr_results", node):
            return

        if isinstance(self.context.get(node.name), Import):
            self.__clobbered(node.name, node)
            return

        with self.enter_class_name(fullname_of(node, safe=True)):
            super().generic_visit(node)

    def visit_For(self, node: ast.For | ast.AsyncFor) -> None:
        names = [n for n in unravel_names(node.target)]

        for import_ in imports_in_names(names, context=self.context):
            self.__clobbered(import_.name, node)

        return super().generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        return self.visit_For(node)

    def visit_With(self, node: ast.With | ast.AsyncWith) -> None:
        for item in node.items:
            if item.optional_vars is None:
                continue

            names = [n for n in unravel_names(item.optional_vars)]

            for import_ in imports_in_names(names, context=self.context):
                self.__clobbered(import_.name, node)

        return super().generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        return self.visit_With(node)

    def check_comprehension(
        self,
        node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp,
    ) -> None:
        for generator in node.generators:
            names = [n for n in unravel_names(generator.target)]

            for import_ in imports_in_names(names, context=self.context):
                self.__clobbered(import_.name, node)

        return super().generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self.check_comprehension(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self.check_comprehension(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self.check_comprehension(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self.check_comprehension(node)
