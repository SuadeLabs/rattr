from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import attrs

from rattr import error
from rattr.ast.util import (
    assignment_is_one_to_one,
    assignment_targets,
    fullname_of,
    has_lambda_in_rhs,
    has_namedtuple_declaration_in_rhs,
    is_relative_import,
    is_starred_import,
    namedtuple_init_signature_from_declaration,
    walruses_in_rhs,
)
from rattr.codegen import gen_import_from_stmt
from rattr.config import Config
from rattr.extra import DictChanges
from rattr.models.context._context import Context
from rattr.models.context._symbol_table import SymbolTable
from rattr.models.symbol._symbols import (
    PYTHON_BUILTINS,
    Builtin,
    CallInterface,
    Class,
    Func,
    Import,
    Name,
)
from rattr.module_locator.util import (
    derive_absolute_module_name,
    derive_module_name_from_path,
    find_module_name_and_spec,
    is_in_import_blacklist,
)

if TYPE_CHECKING:
    from typing import Final

    from rattr.ast.types import Identifier
    from rattr.module_locator.util import ModuleName


# TODO
#   It would be nice to derive these automatically as with the builtins.
#   However, this should always be the union of the appropriate attrs for all supported
#   Python versions as we have no way of knowing which version of Python the targeted
#   source file is using.
MODULE_LEVEL_DUNDER_ATTRS: Final = (
    "__annotations__",
    "__builtins__",
    "__cached__",
    "__doc__",
    "__file__",
    "__loader__",
    "__name__",
    "__package__",
    "__spec__",
)
"""The dunder attrs provided by the interpreter at module level, such as `__file``."""


def compile_root_context(module: ast.Module) -> Context:
    if not isinstance(module, ast.Module):
        raise TypeError("The root context must be derived from a module")

    root = Context(parent=None, symbol_table=SymbolTable())

    # Add the Python default names/builtins with dummy tokens (for a consistent symbol
    # interface).
    root.add([__module_level_name(name) for name in MODULE_LEVEL_DUNDER_ATTRS])
    root.add([__module_level_builtin(name) for name in PYTHON_BUILTINS])

    # Populate the context with the top-level declarations
    _root_context_builder = RootContextBuilder(context=root)
    _root_context_builder.register_stmts(*module.body)

    return root


class RootContextBuilder:
    def __init__(self, context: Context) -> None:
        self.context: Context = context
        super().__init__()

    def register(self, node: ast.AST) -> None:
        if isinstance(node, ast.Module):
            return TypeError("use register_stmts(module.body) for modules")

        # NOTE
        # We do this and implement "visit_If", etc rather than inheriting from
        # `ast.NodeVisitor` as we only want to visit the top-level (i.e. not statements
        # in function or class definitions) statements not every
        # node at every depth.
        visit_method_name = f"visit_{node.__class__.__name__}"
        visit = getattr(self, visit_method_name, None)

        if visit is None:
            return

        return visit(node)

    def register_stmts(self, *stmts: ast.stmt) -> None:
        for stmt in stmts:
            self.register(stmt)

    # ================================================================================ #
    # Registration methods
    # ================================================================================ #

    def visit_Import(self, node: ast.Import) -> None:
        """Register an import.

        >>> import math
        Import(name="math", qualified_name="math")

        >>> import math as m
        Import(name="m", qualified_name="math")

        >>> import math, more_math
        Import(name="math", qualified_name="math")
        Import(name="more_math", qualified_name="more_math")
        """
        if len(node.names) > 1:
            error.info("do not import multiple modules on one line", culprit=node)

        self.context.add(
            make_import_symbol(
                name=alias.asname or alias.name,
                qualified_name=alias.name,
                module_name=alias.name,
                token=node,
            )
            for alias in node.names
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Register an import-from.

        >>> # Regular (named) import
        >>> from math import pi
        Import(name="pi", qualified_name="math.pi")

        >>> # Regular (named) import with alias
        >>> from math import pi as pie
        Import(name="pie", qualified_name="math.pi")

        >>> # Starred-import
        >>> from math import *
        Import(name="*", qualified_name="math")

        >>> # Relative import
        >>> from .relative.module import my_function

        >>> # Relative starred import
        >>> from .relative.module import *

        >>> # Relative starred import from local dir
        >>> from . import module
        """
        # Warn when using starred imports outside of __init__.py
        # There is little good about starred imports (and no benefit over
        # `import numpy as np`, for example), and many issues such as clobbering, etc.
        if is_starred_import(node) and not self.context.is_init_file:
            error_starred_import_outside_init(node, node.module or node.names[0].name)

        # Dispatch to specific import-type handler
        if is_relative_import(node) and is_starred_import(node):
            return self.visit_starred_relative_import(node)
        elif is_relative_import(node):
            return self.visit_relative_import(node)
        elif is_starred_import(node):
            return self.visit_starred_import(node)
        else:
            return self.visit_named_import(node)

    def visit_starred_relative_import(self, node: ast.ImportFrom) -> None:
        config = Config()
        base = derive_module_name_from_path(config.state.current_file)

        if base is None:
            raise ValueError  # only when the file can't be a module, so never here

        module_name = derive_absolute_module_name(base, node.module, node.level)
        (confirmed_module_name, spec) = find_module_name_and_spec(module_name)

        if spec is None:
            error.error("unable to resolve relative starred import", culprit=node)

        if (confirmed_module_name, spec) != (None, None):
            assert module_name == confirmed_module_name  # should always pass

        self.context.add(
            make_import_symbol(
                name="*",
                qualified_name=module_name,
                module_name=module_name,
                token=node,
            )
        )

    def visit_relative_import(self, node: ast.ImportFrom) -> None:
        config = Config()
        base = derive_module_name_from_path(config.state.current_file)

        if base is None:
            raise ValueError  # only when the file can't be a module, so never here

        module_name = derive_absolute_module_name(base, node.module, node.level)
        (confirmed_module_name, spec) = find_module_name_and_spec(module_name)

        if spec is None:
            error.error("unable to resolve relative import", culprit=node)

        if (confirmed_module_name, spec) != (None, None):
            assert module_name == confirmed_module_name  # should always pass

        self.context.add(
            make_import_symbol(
                name=target.asname or target.name,
                qualified_name=f"{module_name}.{target.name}",
                module_name=module_name,
                token=node,
            )
            for target in node.names
        )

    def visit_starred_import(self, node: ast.ImportFrom) -> None:
        if node.module is None:
            error.fatal("node has no module", culprit=node)

        self.context.add(
            make_import_symbol(
                name="*",
                qualified_name=node.module,
                module_name=node.module,
                token=node,
            )
        )

    def visit_named_import(self, node: ast.ImportFrom) -> None:
        if node.module is None:
            error.fatal("node has no module", culprit=node)

        self.context.add(
            make_import_symbol(
                name=target.asname or target.name,
                qualified_name=f"{node.module}.{target.name}",
                module_name=node.module,
                token=node,
            )
            for target in node.names
        )

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit_assignment(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit_assignment(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit_assignment(node)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit_assignment(node)

    def visit_assignment(
        self,
        node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr,
    ) -> None:
        targets = assignment_targets(node)

        if has_lambda_in_rhs(node):
            if not assignment_is_one_to_one(node):
                return error.error("lambda assignment must be one-to-one", culprit=node)

            name = fullname_of(targets[0])
            interface = CallInterface.from_fn_def(node.value)

            self.context.add(Func(name=name, token=node, interface=interface))

        elif has_namedtuple_declaration_in_rhs(node):
            if not assignment_is_one_to_one(node):
                return error.error(
                    "namedtuple assignment must be one-to-one",
                    culprit=node,
                )

            name = fullname_of(targets[0])

            try:
                arguments = namedtuple_init_signature_from_declaration(node)
            except ValueError as exc:
                return error.error(str(exc.args[0]), culprit=node)

            interface = CallInterface(args=arguments)

            self.context.add(Class(name, token=node, interface=interface))

        else:
            for walrus in walruses_in_rhs(node):
                with DictChanges(
                    self.context.symbol_table,
                    iter_items=lambda t: t.values(),
                ) as diff:
                    self.visit_NamedExpr(walrus)

                # Handle `outer_lhs = (inner_lhs := lambda: ...)`
                if has_lambda_in_rhs(walrus):
                    if len(diff.added) == 1 and node.value == walrus:
                        inner_rhs = list(diff.added)[0]
                        outer_lhs = attrs.evolve(
                            inner_rhs,
                            name=fullname_of(assignment_targets(node)[0]),
                        )
                        self.context.add(outer_lhs)
                    elif len(diff.added) > 1:
                        error.error("multiple deeply nested walrus assignments")
                        continue

            for target in targets:
                self.context.add_identifiers_to_context(target)

    def visit_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            self.context.remove_identifiers_from_context(target)

        error.warning(
            "avoid using 'del' at the module level as the target will be undefined so "
            "far as rattr is concerned",
            culprit=node,
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.context.add(Func.from_fn_def(node))

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.context.add(Func.from_fn_def(node))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.context.add(Class.from_class_def(node))

    def visit_If(self, node: ast.If) -> None:
        self.register_stmts(*node.body, *node.orelse)

    def visit_For(self, node: ast.For) -> None:
        self.register_stmts(*node.body, *node.orelse)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.register_stmts(*node.body, *node.orelse)

    def visit_While(self, node: ast.While) -> None:
        self.register_stmts(*node.body, *node.orelse)

    def visit_Try(self, node: ast.Try) -> None:
        self.register_stmts(
            *node.body,
            *node.orelse,
            *node.finalbody,
            *(stmt for handler in node.handlers for stmt in handler.body),
        )

    def visit_With(self, node: ast.With) -> None:
        self.register_stmts(*node.body)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self.register_stmts(*node.body)

    def visit_Expr(self, node: ast.Expr) -> None:
        if isinstance(node.value, ast.Constant):
            return None

        if isinstance(node.value, ast.Call):
            return None

        if isinstance(node.value, ast.Lambda):
            return error.error("top-level lambdas must be named", culprit=node)

        name = node.__class__.__name__
        return error.error(f"unexpected top-level 'ast.{name}'", culprit=node)


def make_import_symbol(
    *,
    name: str,
    qualified_name: str,
    module_name: str,
    token: ast.Import | ast.ImportFrom,
) -> Import:
    """Return the import symbol for the given data, with error checking applied."""
    _import = Import(
        name=name,
        qualified_name=qualified_name,
        token=token,
    )

    # Don't require that blacklisted modules be locatable
    if is_in_import_blacklist(module_name):
        return _import

    # Ensure that we can follow the import
    if _import.origin is None:
        error.fatal(f"unable to find module {module_name!r}", culprit=token)

    return _import


def __dummy_token(name: Identifier) -> ast.Name:
    return ast.Name(
        id=name,
        lineno=0,
        col_offset=0,
        expr_context=ast.expr_context(),
    )


def __module_level_name(name: Identifier) -> Name:
    return Name(name=name, token=__dummy_token(name))


def __module_level_builtin(name: Identifier) -> Builtin:
    return Builtin(name=name, token=__dummy_token(name))


def error_starred_import_outside_init(
    node: ast.ImportFrom,
    module: ModuleName,
) -> None:
    code = gen_import_from_stmt(module, "*")
    message = f"do not use {code!r} outside of __init__.py files, be explicit"
    error.warning(message, culprit=node)
