"""Assert that there are no assignment to names that identify imports."""
from __future__ import annotations

import ast
from contextlib import contextmanager
from typing import TYPE_CHECKING

from rattr.analyser.base import Assertor
from rattr.analyser.types import AnyAssign, AnyFunctionDef, Comprehension
from rattr.analyser.util import (
    get_fullname,
    get_function_def_args,
    has_annotation,
    unravel_names,
)

if TYPE_CHECKING:
    from typing import Generator


def get_lhs_names(lhs: AnyAssign) -> list[str]:
    """Return the names in the lhs of the given assignment."""
    if hasattr(lhs, "targets"):
        targets = lhs.targets
    else:
        targets = [lhs.target]

    return [n for t in targets for n in unravel_names(t, get_name=get_fullname)]


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
        self.failed(f"redefinition of imported name '{name}'", node)

    def __deleted(self, name: str, node: ast.AST) -> None:
        self.failed(f"attempt to delete imported name '{name}'", node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for name in filter(self.context.is_import, get_lhs_names(node)):
            self.__clobbered(name, node)

        return super().generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        for name in filter(self.context.is_import, get_lhs_names(node)):
            self.__clobbered(name, node)

        return super().generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        for name in filter(self.context.is_import, get_lhs_names(node)):
            self.__clobbered(name, node)

        return super().generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        for name in filter(self.context.is_import, get_lhs_names(node)):
            self.__deleted(name, node)

        return super().generic_visit(node)

    def visit_FunctionDef(self, node: AnyFunctionDef) -> None:
        if has_annotation("rattr_ignore", node):
            return

        if has_annotation("rattr_results", node):
            return

        is_in_method = self.class_stack != []

        if not is_in_method and self.context.is_import(node.name):
            return self.__clobbered(node.name, node)

        self.check_arguments(node)

        return super().generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return self.visit_FunctionDef(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.check_arguments(node)
        return super().generic_visit(node)

    def check_arguments(self, node: AnyFunctionDef) -> None:
        args, vararg, kwarg = get_function_def_args(node)
        names = {a for a in (*args, vararg, kwarg) if a is not None}

        for name in filter(lambda n: self.context.is_import(n), names):
            self.__clobbered(name, node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if has_annotation("rattr_ignore", node):
            return

        if has_annotation("rattr_results", node):
            return

        if self.context.is_import(node.name):
            self.__clobbered(node.name, node)
            return

        with self.enter_class_name(get_fullname(node, safe=True)):
            super().generic_visit(node)

    def visit_For(self, node: ast.For | ast.AsyncFor) -> None:
        names = [n for n in unravel_names(node.target)]

        for name in filter(lambda n: self.context.is_import(n), names):
            self.__clobbered(name, node)

        return super().generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        return self.visit_For(node)

    def visit_With(self, node: ast.With | ast.AsyncWith) -> None:
        for item in node.items:
            if item.optional_vars is None:
                continue

            names = [n for n in unravel_names(item.optional_vars)]

            for name in filter(lambda n: self.context.is_import(n), names):
                self.__clobbered(name, node)

        return super().generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        return self.visit_With(node)

    def check_comprehension(self, node: Comprehension | ast.GeneratorExp) -> None:
        for generator in node.generators:
            names = [n for n in unravel_names(generator.target)]

            for name in filter(lambda n: self.context.is_import(n), names):
                self.__clobbered(name, node)

        return super().generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self.check_comprehension(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self.check_comprehension(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self.check_comprehension(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self.check_comprehension(node)
