"""Rattr file analyser."""
from __future__ import annotations

import ast
import copy
from collections import deque
from typing import NamedTuple

import attrs

from rattr import error
from rattr.analyser.base import NodeVisitor
from rattr.analyser.cls import ClassAnalyser
from rattr.analyser.function import FunctionAnalyser
from rattr.analyser.types import ImportsIr
from rattr.analyser.util import (
    has_annotation,
    is_blacklisted_module,
    is_excluded_name,
    is_pip_module,
    is_stdlib_module,
    parse_rattr_results_from_annotation,
    read,
    timer,
)
from rattr.ast.types import AnyAssign, AnyFunctionDef
from rattr.ast.util import (
    assignment_is_one_to_one,
    assignment_targets,
    fullname_of,
    has_lambda_in_rhs,
    has_namedtuple_declaration_in_rhs,
    walruses_in_rhs,
)
from rattr.config import Config
from rattr.config.state import enter_file
from rattr.extra import DictChanges
from rattr.models.context import Context, compile_root_context
from rattr.models.ir import FileIr
from rattr.models.symbol import Import
from rattr.plugins import plugins


class RattrStats(NamedTuple):
    parse_time: float
    root_context_time: float
    assert_time: float
    analyse_imports_time: float
    analyse_file_time: float

    file_lines: int
    import_lines: int

    number_of_imports: int
    number_of_unique_imports: int


class RattrImportStats(NamedTuple):
    import_lines: int
    number_of_imports: int
    number_of_unique_imports: int


def parse_and_analyse_file() -> tuple[FileIr, ImportsIr, RattrStats]:
    """Parse and analyse the target file from the config."""
    config = Config()

    with enter_file(config.arguments.target):
        file_ir, imports_ir, stats = __parse_and_analyse_file_impl()

    return file_ir, imports_ir, stats


def __parse_and_analyse_file_impl() -> tuple[FileIr, ImportsIr, RattrStats]:
    """Parse and analyse the given file contents."""
    config = Config()

    with timer() as parse_timer, read(config.arguments.target) as (file_lines, source):
        ast_module = ast.parse(source)

    with timer() as root_context_timer:
        context = compile_root_context(ast_module).expand_starred_imports()

    with timer() as assert_timer:
        for assertor in plugins.assertors:
            assertor.assert_holds(ast_module, copy.deepcopy(context))

    with timer() as analyse_imports_timer:
        if config.arguments.follow_imports:
            symbols = context.symbol_table.symbols()
            imports = [s for s in symbols if isinstance(s, Import)]
            imports_ir, import_stats = parse_and_analyse_imports(imports)
        else:
            imports_ir, import_stats = {}, RattrImportStats(0, 0, 0)

    with timer() as analyse_file_timer:
        file_ir = FileAnalyser(ast_module, context).analyse()

    stats = RattrStats(
        parse_timer.time,
        root_context_timer.time,
        assert_timer.time,
        analyse_imports_timer.time,
        analyse_file_timer.time,
        file_lines,
        import_stats.import_lines,
        import_stats.number_of_imports,
        import_stats.number_of_unique_imports,
    )
    return file_ir, imports_ir, stats


def parse_and_analyse_imports(
    imports: list[Import],
) -> tuple[ImportsIr, RattrImportStats]:
    """Return the mapping from file name to IR for each import.

    Imports are a directed cyclic graph, however, previously analysed files can
    just be ignored (analysing is deterministic and context-free). Thus, the
    graph of imports becomes a DAG which we BFS.
    """
    config = Config()
    queue = deque(imports)

    import_irs: ImportsIr = {}
    import_stats = RattrImportStats(0, 0, 0)

    seen_module_origins: set[str] = set()

    while queue:
        import_ = queue.popleft()
        import_stats.number_of_imports += 1

        name = import_.module_name
        spec = import_.module_spec

        if name is None:
            error.error(f"unable to resolve import {import_.qualified_name!r}")
            continue

        if spec is None:
            error.error(f"unable to resolve module spec for {name!r}")
            continue

        if spec.origin is None:
            # HACK Can't use isinstance
            # TODO Resolve BuiltinImporter modules
            if "BuiltinImporter" in str(spec.loader):
                error.error(f"unable to resolve builtin module {name!r}", badness=0)
            else:
                error.error(f"unable to resolve import {import_.qualified_name!r}")
            continue

        if spec.origin in seen_module_origins:
            continue

        if is_blacklisted_module(name):
            continue

        if not config.arguments.follow_pip_imports and is_pip_module(name):
            continue

        if not config.arguments.follow_stdlib_imports and is_stdlib_module(name):
            continue

        with read(spec.origin) as (import_file_lines, import_file_source):
            import_ast = ast.parse(import_file_source)

        with enter_file(spec.origin):
            import_context = compile_root_context(import_ast).expand_starred_imports()
            import_ir = FileAnalyser(import_ast, import_context).analyse()

        import_irs[name] = import_ir

        imports_in_the_current_import = [
            symbol
            for symbol in import_context.symbol_table.symbols
            if isinstance(symbol, Import)
        ]
        for next_import in imports_in_the_current_import:
            queue.append(next_import)

        import_stats.import_lines += import_file_lines

        seen_module_origins.add(spec.origin)

    import_stats.number_of_unique_imports = len(seen_module_origins)
    return import_irs, import_stats



class FileAnalyser(NodeVisitor):
    """Walk a file's AST and analyse the contained functions and classes."""

    def __init__(self, _ast: ast.Module, context: Context) -> None:
        """Set configuration and initialise results."""
        self._ast = _ast
        self.context = context
        self.file_ir = FileIr(context=context)

    def analyse(self) -> FileIr:
        """Entry point of FileAnalyser, return the results of analysis."""
        self.visit(self._ast)

        return self.file_ir

    def visit_AnyFunctionDef(self, node: AnyFunctionDef) -> None:
        if has_annotation("rattr_ignore", node):
            return

        if is_excluded_name(node.name):
            return

        try:
            fn = self.context.get_func_or_error(node.name)
        except KeyError as exc:
            return error.error(str(exc.args[0]), culprit=node)

        if has_annotation("rattr_results", node):
            self.file_ir[fn] = parse_rattr_results_from_annotation(node, self.context)
            return

        if plugins.custom_function_handler.has_analyser(node.name, self.context):
            handler = plugins.custom_function_handler.get(node.name, self.context)
            self.file_ir[fn] = handler.on_def(node.name, node, self.context)
            return

        self.file_ir[fn] = FunctionAnalyser(node, self.context).analyse()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.visit_AnyFunctionDef(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_AnyFunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if has_annotation("rattr_ignore", node):
            return

        if is_excluded_name(node.name):
            return

        class_ir = ClassAnalyser(node, self.context).analyse()

        for foc, foc_ir in class_ir.items():
            self.file_ir[foc] = foc_ir

    # ----------------------------------------------------------------------- #
    # Lambdas
    # ----------------------------------------------------------------------- #

    def visit_LambdaAssign(self, node: AnyAssign) -> None:
        if not assignment_is_one_to_one(node):
            return error.fatal("lambda assignment must be one-to-one", node)

        targets = assignment_targets(node)
        name = fullname_of(targets[0])

        try:
            fn = self.context.get_func_or_error(name)
        except KeyError as exc:
            return error.error(str(exc.args[0]), culprit=node)

        self.file_ir[fn] = FunctionAnalyser(node.value, self.context).analyse()

    def visit_NamedTupleAssign(self, node: AnyAssign) -> None:
        if not assignment_is_one_to_one(node):
            return error.fatal("namedtuple assignment must be one-to-one", node)

        name = fullname_of(assignment_targets(node)[0])

        try:
            cls = self.context.get_class_or_error(name)
        except KeyError as exc:
            return error.error(str(exc.args[0]), culprit=node)

        self.file_ir[cls] = {
            "gets": set(),
            "sets": set(),
            "dels": set(),
            "calls": set(),
        }

    def visit_AnyAssign(self, node: AnyAssign) -> None:
        if has_lambda_in_rhs(node):
            self.visit_LambdaAssign(node)

        if has_namedtuple_declaration_in_rhs(node):
            self.visit_NamedTupleAssign(node)

        # Walrus may obscure a lambda, so peek in and visit the nice walruses
        for walrus in walruses_in_rhs(node):
            with DictChanges(self.file_ir) as diff:
                self.visit_AnyAssign(walrus)

            # Handle `outer_lhs = (inner_lhs := lambda: ...)`
            if has_lambda_in_rhs(walrus):
                if len(diff.added) == 1 and node.value == walrus:
                    inner_rhs = list(diff.added)[0]
                    outer_lhs = attrs.evolve(
                        inner_rhs,
                        name=fullname_of(assignment_targets(node)[0]),
                    )
                    self.file_ir[outer_lhs] = self.file_ir[inner_rhs]
                elif len(diff.added) > 1:
                    raise NotImplementedError("Multiple deeply nested walruses")

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit_AnyAssign(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit_AnyAssign(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit_AnyAssign(node)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit_AnyAssign(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # NOTE Only reached when the lambda is an anonymous function
        return error.fatal("module level lambdas unsupported", node)
