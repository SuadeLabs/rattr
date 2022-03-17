"""Rattr analyser context and utilities.

A context holds a symbol table for a given scope (file, function, class, etc)
within a given file. All contexts for a file for a tree with unidirectional
references from child context to parent context.

The root context of a file contains, amongst other things, the Python builtin
functions such as `print`, etc.

"""

import ast
from contextlib import contextmanager
from typing import Any, Generator, Iterable, Optional, Set, TypeVar, Union

from rattr import config, error
from rattr.analyser.context.symbol import (
    Builtin,
    CallTarget,
    Class,
    Func,
    Import,
    Name,
    Symbol,
    get_module_name_and_spec,
    get_possible_module_names,
)
from rattr.analyser.context.symbol_table import SymbolTable
from rattr.analyser.types import AnyAssign, Constant, Literal
from rattr.analyser.util import (
    PYTHON_BUILTINS,
    assignment_is_one_to_one,
    enter_file,
    get_absolute_module_name,
    get_assignment_targets,
    get_fullname,
    get_function_def_args,
    get_starred_imports,
    has_affect,
    is_blacklisted_module,
    is_method_on_primitive,
    is_relative_import,
    is_starred_import,
    lambda_in_rhs,
    module_name_from_file_path,
    remove_call_brackets,
    unravel_names,
)

_Context = TypeVar("_Context", bound="Context")


@contextmanager
def new_context(container: Any) -> Generator:
    """Push then pop a new context."""
    if not hasattr(container, "context"):
        raise AttributeError("'container' needs the attribute 'context'")

    parent = container.context
    container.context = Context(parent)
    yield
    container.context = parent


class Context:
    """Hold the context for some scope.

    A context and it's parent, parent's parent, etc form a tree of contexts
    that correlates with the AST of the related file.

    The parent and the parent's parent, etc of a context, C, are collectively
    refferred to as the "ancestors" of C.

    """

    def __init__(self, parent: Optional[_Context]) -> None:
        self.parent = parent
        self.symbol_table = SymbolTable()
        self.file = config.current_file

    def add(self, symbol: Symbol, is_argument: bool = False) -> None:
        """Add the given symbol to the context.

        If the symbol is already present in the context, or an ancestor, then
        it will not be re-added.

        If the symbol `is_argument`, then the symbol will always be added
        regardless of whether-or-not it is declared in an ancestor.

        """
        if not is_argument and symbol in self:
            return

        self.symbol_table.add(symbol)

    def add_all(self, symbols: Iterable[Symbol]) -> None:
        """Add all of the given symbols (assumes none are arguments)."""
        for s in symbols:
            self.add(s)

    def remove(self, name: str) -> None:
        """Remove the symbol matching the given name from the context."""
        if self.declares(name):
            self.symbol_table.remove(name)
            return

        if self.parent is None:
            return

        self.parent.remove(name)

    def remove_all(self, names: Iterable[str]) -> None:
        """Remove all of the given symbols."""
        for n in names:
            self.remove(n)

    def get(self, name: str) -> Optional[Symbol]:
        """Return the symbol matching `name`, in this context or an ancestor.

        If `name` exists in some context, C, and an ancestor of C, then the
        most constrained (closet) definition is used -- i.e. the definition in
        C.

        """
        if self.parent is None:
            return self.symbol_table.get(name)

        return self.symbol_table.get(name) or self.parent.get(name)

    def get_call_target(
        self, callee: str, culprit: ast.Call, warn: bool = True
    ) -> Optional[Symbol]:
        """Return the target of the given AST call, if within the context."""
        if not isinstance(callee, str) or not callee.endswith("()"):
            raise ValueError("'callee' must a string ending with '()'")

        name = remove_call_brackets(callee).replace("*", "")
        stripped = name.replace("*", "").replace("[]", "").replace("()", "")

        if stripped.startswith("@"):
            return None

        target = self.get(name)

        # NOTE
        #   Method on some LHS in context, but not a call to an implicitly
        #   imported function
        _lhs_target = self.get(stripped.split(".")[0])
        if target is None and not isinstance(_lhs_target, Import):
            target = _lhs_target

        # NOTE
        #   If target is not defined locally (or explicitly imported locally),
        #   it could be implicitly imported.
        #       `from math import pi`   ->  explicitly imported as `pi`
        #       `import math`           ->  implicitly imported as `math.pi`
        if target is None:
            modules = map(self.get, get_possible_module_names(stripped))
            defined = list(filter(lambda m: m is not None, modules))
            _lhs_target = next(iter(defined), None)

            if isinstance(_lhs_target, Import):
                local_name = name.replace(f"{_lhs_target.name}.", "")
                qualified_name = f"{_lhs_target.qualified_name}.{local_name}"
                target = Import(name, qualified_name)
            else:
                target = _lhs_target

        # NOTE
        #   If declared in this scope and called, it is likely an argument or a
        #   lambda (handled elsewhere).
        #   If it is an argument, then it is either a procedural parameter or a
        #   call to a method on an argument; distinguished by "." being in the
        #   callee name.
        if warn and target is not None and not isinstance(target, CallTarget.__args__):
            if "." not in callee and self.declares(target.name):
                error.error(
                    f"unable to resolve call to '{name}', likely a procedural "
                    f"parameter",
                    culprit,
                )
            elif "." in callee:
                # TODO Once method support is added, elevate this to an error
                error.info(f"unable to resolve call to method '{name}'", culprit)
            else:
                error.error(f"'{name}' is not callable", culprit)

        if warn and target is None and not is_method_on_primitive(name):
            error.error(f"unable to resolve call to '{name}'", culprit)

        if warn and target is not None and callee.endswith("()()"):
            error.warning("unable to resolve call result of call", culprit)

        return target

    def declares(self, name: str) -> bool:
        """Return `True` if `name` was declared in this context."""
        return name in self.symbol_table.names()

    def __contains__(self, symbol: Union[str, Symbol]) -> bool:
        """Return `True` if `symbol` was declared in this or an ancestor."""
        name = symbol if isinstance(symbol, str) else symbol.name

        if self.parent is None:
            return self.declares(name)

        return self.declares(name) or (name in self.parent)

    def get_root(self) -> _Context:
        """Return the root context for the related file."""
        if self.parent is None:
            return self

        return self.parent.get_root()

    def is_import(self, name: str) -> bool:
        """Return `True` if `name` refferres to an import in this context."""
        return isinstance(self.get(name), Import)

    # ----------------------------------------------------------------------- #
    # Registration helpers
    # ----------------------------------------------------------------------- #

    def add_identifiers_to_context(self, assignment: ast.expr) -> None:
        for name in unravel_names(assignment):
            self.add(Name(name))

    def del_identifiers_from_context(self, assignment: ast.expr):
        for name in unravel_names(assignment):
            self.remove(name)

    def push_arguments_to_context(self, arguments: ast.arguments) -> None:
        all_arguments = [*arguments.args, arguments.vararg, arguments.kwarg]

        for arg in [a for a in all_arguments if a]:
            self.add(Name(arg.arg), is_argument=True)

    # ----------------------------------------------------------------------- #
    # Syntactic sugar
    # ----------------------------------------------------------------------- #

    def expand_starred_imports(self) -> _Context:
        """Expand starred imports to normal imports."""
        seen: Set[str] = set()

        # Create initial starred list for BFS
        starred = get_starred_imports(self.symbol_table.symbols(), seen)

        # BFS the unseen * imports
        for _i in starred:
            if _i.module_spec is None or _i.module_spec.origin is None:
                error.error(
                    f"unable to resolve import '{_i.name}' while expanding "
                    f"syntactic sugar 'from {_i.qualified_name} import *' "
                    f"in {self.file}"
                )
                continue

            if _i.module_spec.origin in seen:
                continue

            with open(_i.module_spec.origin, "r") as f:
                _i_ast = ast.parse(f.read())

            with enter_file(_i.module_spec.origin):
                _i_ctx = RootContext(_i_ast)

            seen.add(_i.module_spec.origin)

            starred += get_starred_imports(_i_ctx.symbol_table.symbols(), seen)

            # Tread `from x import *` as syntactic sugar for
            # `from x import a, b, c, ...`
            for s in _i_ctx.symbol_table.symbols():
                self.add(Import(s.name, f"{_i.qualified_name}.{s.name}"))

        return self


def _new_import_symbol(
    name: str,
    qualified_name: str,
    module: str,
    node: ast.AST,
) -> Import:
    """Return the Import symbol for the given name; warn if spec not found."""
    if not isinstance(node, (ast.Import, ast.ImportFrom)):
        raise TypeError

    _import = Import(name, qualified_name)

    if is_blacklisted_module(module):
        return _import

    if _import.module_spec is None:
        error.fatal(f"unable to find module '{module}'", node)

    return _import


class RootContext(Context):
    """Return the root context for the given module.

    Supports:
        * Import, ImportFrom
        * Assign, AugAssign
        * FunctionDef, AsyncFunctionDef
        * ClassDef
        * If
        * For, AsyncFor
        * While
        * Try
        * With, AsyncWith

    """

    module_level_attributes = [
        "__annotations__",
        "__builtins__",
        "__cached__",
        "__doc__",
        "__file__",
        "__loader__",
        "__name__",
        "__package__",
        "__spec__",
    ]

    def __new__(self, module: ast.Module) -> Any:  # Context, make mypy happy
        if not isinstance(module, ast.Module):
            raise TypeError("The root context can only exist for a module")

        context = Context(None)

        # Register Python module level attributes
        for attribute in RootContext.module_level_attributes:
            context.add(Name(attribute))

        # Register the Python builtins
        for name in PYTHON_BUILTINS:
            context.add(Builtin(name, has_affect=has_affect(name)))

        # Register the top-level symbols
        for node in module.body:
            RootContext.register(context, node)

        return context

    @staticmethod
    def register(context: Context, node: ast.AST) -> None:
        """Register the given node."""
        name = node.__class__.__name__
        register_method = getattr(RootContext, f"register_{name}", None)

        if not register_method:
            error.fatal("unsupported top-level statement", node)
            return

        return register_method(context, node)

    # ----------------------------------------------------------------------- #
    # Registration, self is of type Context @see __new__() and register()
    # ----------------------------------------------------------------------- #

    def register_Import(self, node: ast.Import) -> None:
        """Register the given imports with qualified names.

        >>> import math
        Import(name="math", qualified_name="math")

        >>> import math as m
        Import(name="m", qualified_name="math")

        >>> import math, more_math
        Import(name="math", qualified_name="math")
        Import(name="more_math", qualified_name="more_math")

        """
        if len(node.names) > 1:
            error.info("do not import multiple modules on oneline", node)

        for module in node.names:
            _import = _new_import_symbol(
                module.asname or module.name, module.name, module.name, node
            )
            self.add(_import)

    def register_starred_import(self, node: ast.ImportFrom) -> None:
        """Helper method for starred imports."""
        if self.file is None or not self.file.endswith("__init__.py"):
            error.warning(
                f"do not use 'from {node.module} import *', be explicit", node
            )

        module = node.module

        # Allow starred imports to be relative
        if node.level > 0:
            base = module_name_from_file_path(config.current_file)
            module = get_absolute_module_name(base, node.level, node.module)

            if get_module_name_and_spec(module) == (None, None):
                error.error("unable to resolve relative starred import", node)

        self.add(_new_import_symbol("*", module, module, node))

    def register_relative_import(self, node: ast.ImportFrom) -> None:
        """Helper method for relative imports."""
        base = module_name_from_file_path(config.current_file)

        if base is None:
            error.fatal("unable to resolve parent in relative import", node)

        module = get_absolute_module_name(base, node.level, node.module)

        if get_module_name_and_spec(module) == (None, None):
            error.error("unable to resolve relative import", node)

        for target in node.names:
            _import = _new_import_symbol(
                target.asname or target.name, f"{module}.{target.name}", module, node
            )
            self.add(_import)

    def register_named_imports(self, node: ast.ImportFrom) -> None:
        """Helper method for named imports, i.e. `from M import name, ...`."""
        for target in node.names:
            _import = _new_import_symbol(
                target.asname or target.name,
                f"{node.module}.{target.name}",
                node.module,
                node,
            )
            self.add(_import)

    def register_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Register the given from-imports with qualified names.

        >>> from math import pi
        Import(name="pi", qualified_name="math.pi")

        >>> from math import pi as pie
        Import(name="pie", qualified_name="math.pi")

        >>> from math import *
        Import(name="*", qualified_name="math")

        """
        if is_starred_import(node):
            RootContext.register_starred_import(self, node)
            return

        if is_relative_import(node):
            RootContext.register_relative_import(self, node)
            return

        RootContext.register_named_imports(self, node)

    def register_AnyAssign(self, node: AnyAssign) -> None:
        targets = get_assignment_targets(node)

        if lambda_in_rhs(node):
            if not assignment_is_one_to_one(node):
                error.fatal("lambda assignment must be one-to-one", node)
            else:
                name = get_fullname(targets[0])
                self.add(Func(name, *get_function_def_args(node.value)))
            return

        for target in targets:
            self.add_identifiers_to_context(target)

    def register_Assign(self, node: ast.Assign) -> None:
        RootContext.register_AnyAssign(self, node)

    def register_AnnAssign(self, node: ast.AnnAssign) -> None:
        RootContext.register_AnyAssign(self, node)

    def register_AugAssign(self, node: ast.AugAssign) -> None:
        RootContext.register_AnyAssign(self, node)

    def register_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            self.del_identifiers_from_context(target)

        error.warning(
            "avoid 'del' at module-level, Rattr will assume the target has "
            "been removed before reaching any child context (functions, "
            "classes, etc)",
            node,
        )

    # ----------------------------------------------------------------------- #
    # Functions, classes, etc
    # ----------------------------------------------------------------------- #

    def register_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.add(Func(node.name, *get_function_def_args(node)))

    def register_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.add(Func(node.name, *get_function_def_args(node), is_async=True))

    def register_ClassDef(self, node: ast.ClassDef) -> None:
        # NOTE
        #   Create as constructor/initialiser-less class, populate those symbol
        #   attributes when analysing the class itself
        self.add(Class(node.name, None, None, None))

    # ----------------------------------------------------------------------- #
    # Top-level blocks of statements
    # ----------------------------------------------------------------------- #

    def register_stmts(self, *stmts) -> None:
        for stmt in stmts:
            RootContext.register(self, stmt)

    def register_If(self, node: ast.If) -> None:
        RootContext.register_stmts(self, *node.body, *node.orelse)

    def register_For(self, node: ast.For) -> None:
        RootContext.register_stmts(self, *node.body, *node.orelse)

    def register_AsyncFor(self, node: ast.For) -> None:
        RootContext.register_stmts(self, *node.body, *node.orelse)

    def register_While(self, node: ast.While) -> None:
        RootContext.register_stmts(self, *node.body, *node.orelse)

    def register_Try(self, node: ast.Try) -> None:
        bodies = node.body + node.orelse + node.finalbody
        handlers = [s for h in node.handlers for s in h.body]

        RootContext.register_stmts(self, *bodies, *handlers)

    def register_With(self, node: ast.With) -> None:
        RootContext.register_stmts(self, *node.body)

    def register_AsyncWith(self, node: ast.AsyncWith) -> None:
        RootContext.register_stmts(self, *node.body)

    # ----------------------------------------------------------------------- #
    # Explicit ignores: docstrings, etc.
    # ----------------------------------------------------------------------- #

    def register_Expr(self, node: ast.Expr) -> None:
        """Ignore standalone expressions.

        Literal | Constant
            Just a value (absent from an assignment, thus ignoreable),
            e.g. a docstring.

        Call
            Likely calling an entry-point or part of configuration -- shouldn't
            affect context and thus can be ignored.

        Lambda
            If lambda is not an assignment RHS or a call argument (i.e. just
            "floating"), then disallow it.

        """
        if isinstance(node.value, Literal.__args__):
            return

        if isinstance(node.value, Constant.__args__):
            return

        if isinstance(node.value, ast.Call):
            return

        if isinstance(node.value, ast.Lambda):
            return error.fatal("top-level lambdas must be named", node)

        _name = node.__class__.__name__
        error.warning(f"unexpected top-level expression 'ast.{_name}'", node)
