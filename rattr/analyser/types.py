"""Rattr types."""

import ast
import json
from typing import (
    Dict,
    ItemsView,
    Iterator,
    KeysView,
    Optional,
    Set,
    Union,
    ValuesView,
)

from rattr.analyser.context.symbol import Class, Func, Symbol

Constant = Union[
    ast.Constant,
    # Deprecated in Python 3.8, replaced with ast.Constant(..., kind=?)
    ast.Num,
    ast.Str,
    ast.Bytes,
    ast.NameConstant,
    ast.Ellipsis,
]

Literal = Union[
    ast.FormattedValue,
    ast.JoinedStr,
    ast.List,
    ast.Tuple,
    ast.Set,
    ast.Dict,
]

Comprehension = Union[
    ast.ListComp,
    ast.SetComp,
    ast.GeneratorExp,
    ast.DictComp,
]


Nameable = ast.expr

# Nodes which contain a name attribute (.func, .id, .attr, etc)
StrictlyNameable = Union[
    ast.Name,
    ast.Attribute,
    ast.Subscript,
    ast.Starred,
    ast.Call,
]

# The subset of `StrictlyNameable` which contain `Name` as their base element
CompoundStrictlyNameable = Union[
    ast.Attribute,
    ast.Subscript,
    ast.Starred,
]

AstDef = Union[
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
]

# Union of Python literals
PythonLiteral = Union[
    None,
    int,
    float,
    complex,
    bool,
    str,
    bytes,
]

FuncOrAsyncFunc = Union[ast.FunctionDef, ast.AsyncFunctionDef]

AnyFunctionDef = Union[
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Lambda,
]


AnyAssign = Union[
    ast.Assign,
    ast.AnnAssign,
    ast.AugAssign,
]


# --------------------------------------------------------------------------- #
# Results and intermediate representation (IR)
# --------------------------------------------------------------------------- #

FuncOrClass = Union[Func, Class]

# LHS: "sets" | "gets" | "calls" | "dels"
FunctionIR = Dict[str, Set[Symbol]]


ClassIR = Dict[FuncOrClass, FunctionIR]


_FileIR = Dict[FuncOrClass, FunctionIR]


class FileIR:
    """Provide a `Mapping[Func, FunctionIR]`, with context."""

    def __init__(self, context):
        # `self.context: Context` omitted to avoid circular import, hopefully
        # mypy's inference is sufficient
        self.context = context
        self._file_ir: _FileIR = dict()

    def __eq__(self, other) -> bool:
        if isinstance(other, dict):
            return other == self._file_ir

        if isinstance(other, FileIR):
            return other.context == self.context and other._file_ir == self._file_ir

        raise TypeError(f"Cannot compare 'FileIR' and '{type(other)}'")

    def __iter__(self) -> Iterator[FuncOrClass]:
        return iter(self._file_ir)

    def __contains__(self, item: FuncOrClass) -> bool:
        return item in self._file_ir

    def __setitem__(self, item: FuncOrClass, value: FunctionIR) -> None:
        self._file_ir[item] = value

    def __getitem__(self, item: FuncOrClass) -> FunctionIR:
        return self._file_ir[item]

    def get(
        self, item: FuncOrClass, default: Optional[FunctionIR] = None
    ) -> Optional[FunctionIR]:
        return self._file_ir.get(item, default)

    def keys(self) -> KeysView[FuncOrClass]:
        return self._file_ir.keys()

    def values(self) -> ValuesView[FunctionIR]:
        return self._file_ir.values()

    def items(self) -> ItemsView[FuncOrClass, FunctionIR]:
        return self._file_ir.items()

    class JsonEncoder(json.JSONEncoder):
        """JSON encoder for FileIR."""

        def default(self, obj):
            if isinstance(obj, set):
                return list(obj)
            if isinstance(obj, Symbol):
                return repr(obj)
            return super().default(obj)

    def __str__(self) -> str:
        cleaned = {repr(k): v for k, v in self._file_ir.items()}

        return json.dumps(cleaned, indent=4, cls=FileIR.JsonEncoder)

    def __repr__(self) -> str:
        return f"FileIR(context={self.context}, _file_ir={self._file_ir}"


# LHS: module fully-qualified name
ImportsIR = Dict[str, FileIR]


# LHS: "sets" | "gets" | "calls" | "dels"
FunctionResults = Dict[str, Set[str]]


# LHS: function name
FileResults = Dict[str, FunctionResults]
