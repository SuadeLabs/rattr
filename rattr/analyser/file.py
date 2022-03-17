"""Rattr file analyser."""

import ast
from collections import namedtuple
from copy import deepcopy
from typing import List, NamedTuple, Set, Tuple

from rattr import config, error
from rattr.analyser.base import NodeVisitor
from rattr.analyser.cls import ClassAnalyser
from rattr.analyser.context import Context, Func, Import, RootContext
from rattr.analyser.function import FunctionAnalyser
from rattr.analyser.types import AnyAssign, AnyFunctionDef, FileIR, ImportsIR
from rattr.analyser.util import (
    assignment_is_one_to_one,
    enter_file,
    get_assignment_targets,
    get_fullname,
    has_annotation,
    is_blacklisted_module,
    is_excluded_name,
    is_pip_module,
    is_stdlib_module,
    lambda_in_rhs,
    parse_rattr_results_from_annotation,
    read,
    timer,
)
from rattr.plugins import plugins

RattrStats = namedtuple(
    "RattrStats",
    [
        "parse_time",
        "root_context_time",
        "assert_time",
        "analyse_imports_time",
        "analyse_file_time",
        "file_lines",
        "import_lines",
        "number_of_imports",
        "number_of_unique_imports",
    ],
)

ImportStats = namedtuple(
    "ImportStats",
    [
        "import_lines",
        "number_of_imports",
        "number_of_unique_imports",
    ],
)


def parse_and_analyse_file() -> Tuple[FileIR, ImportsIR, NamedTuple]:
    """Parse and analyse `config.file`."""
    with enter_file(config.file):
        file_ir, imports_ir, stats = __parse_and_analyse_file()

    return file_ir, imports_ir, stats


def __parse_and_analyse_file() -> Tuple[FileIR, ImportsIR, NamedTuple]:
    """Parse and analyse the given file contents."""
    with timer() as parse_timer, read(config.file) as (file_lines, source):
        _ast = ast.parse(source)

    with timer() as root_context_timer:
        context = RootContext(_ast).expand_starred_imports()

    with timer() as assert_timer:
        for assertor in plugins.assertors:
            assertor.assert_holds(_ast, deepcopy(context))

    with timer() as analyse_imports_timer:
        if config.follow_imports:
            symbols = context.symbol_table.symbols()
            imports = list(filter(lambda s: s._is(Import), symbols))
            imports_ir, import_stats = parse_and_analyse_imports(imports)
        else:
            imports_ir, import_stats = dict(), ImportStats(0, 0, 0)

    with timer() as analyse_file_timer:
        file_ir = FileAnalyser(_ast, context).analyse()

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


def parse_and_analyse_imports(imports: List[Import]) -> Tuple[ImportsIR, ImportStats]:
    """Return the mapping from file name to IR for each import.

    Imports are a directed cyclic graph, however, previously analysed files can
    just be ignored (analysing is deterministic and context-free). Thus, the
    graph of imports becomes a DAG which we BFS.

    """
    n_lines: int = 0
    n_imports: int = 0
    imports_ir: ImportsIR = dict()
    seen_module_paths: Set[str] = set()

    for _i in imports:
        module_name = _i.module_name
        module_path = _i.module_spec.origin

        if module_name is None or module_path is None:
            # HACK Can't use isinstance, TODO Resolve BuiltinImporter modules
            if "BuiltinImporter" in str(_i.module_spec.loader):
                error.error(
                    f"unable to resolve builtin module '{module_name}'", badness=0
                )
                continue

            error.fatal(f"unable to resolve import '{_i.qualified_name}'")
            continue

        if module_path in seen_module_paths:
            continue

        if is_blacklisted_module(module_name):
            continue

        if not config.follow_pip_imports and is_pip_module(module_name):
            continue

        if not config.follow_stdlib_imports and is_stdlib_module(module_name):
            continue

        with read(module_path) as (file_lines, source):
            _i_ast = ast.parse(source)

        with enter_file(module_path):
            _i_ctx = RootContext(_i_ast).expand_starred_imports()
            _i_ir = FileAnalyser(_i_ast, _i_ctx).analyse()

        imports_ir[module_name] = _i_ir

        # Add the import's imports to the queue
        _i_imports = list(
            filter(lambda s: s._is(Import), _i_ctx.symbol_table.symbols())
        )
        imports += _i_imports

        n_lines += file_lines
        n_imports += len(_i_imports)

        seen_module_paths.add(module_path)

    return imports_ir, ImportStats(n_lines, n_imports, len(seen_module_paths))


class FileAnalyser(NodeVisitor):
    """Walk a file's AST and analyse the contained functions and classes."""

    def __init__(self, _ast: ast.Module, context: Context) -> None:
        """Set configuration and initialise results."""
        self._ast = _ast
        self.context = context
        self.file_ir = FileIR(context)

    def analyse(self) -> FileIR:
        """Entry point of FileAnalyser, return the results of analysis."""
        self.visit(self._ast)

        return self.file_ir

    def visit_AnyFunctionDef(self, node: AnyFunctionDef) -> None:
        if has_annotation("rattr_ignore", node):
            return

        if is_excluded_name(node.name):
            return

        fn: Func = self.context.get(node.name)

        if has_annotation("rattr_results", node):
            self.file_ir[fn] = parse_rattr_results_from_annotation(node, self.context)
            return

        if plugins.custom_function_handler.has_analyser(node.name, self.context):
            self.file_ir[fn] = plugins.custom_function_handler.get(
                node.name, self.context
            ).on_def(node.name, node, self.context)
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

    def visit_AnyAssign(self, node: AnyAssign) -> None:
        if not lambda_in_rhs(node):
            return

        if not assignment_is_one_to_one(node):
            error.fatal("lambda assignment must be one-to-one", node)
            return

        targets = get_assignment_targets(node)
        name = get_fullname(targets[0])

        fn, context = self.context.get(name), self.context
        self.file_ir[fn] = FunctionAnalyser(node.value, context).analyse()

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit_AnyAssign(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit_AnyAssign(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit_AnyAssign(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # NOTE Only reached when the lambda is an anonymous function
        return error.fatal("module level lambdas unsupported", node)

    # ----------------------------------------------------------------------- #
    # Walrus Operator
    # ----------------------------------------------------------------------- #

    def visit_NamedExpr(self, node) -> None:
        return error.fatal("walrus operator is currently unsupported", node)
