from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

import attrs
from cattrs.preconf.json import make_converter

from rattr.models.context import Context, SymbolTable
from rattr.models.ir import FileIr
from rattr.models.results import FileResults
from rattr.models.symbol import Symbol

if TYPE_CHECKING:
    from typing import Any, TypeVar

    from rattr.versioning.typing import TypeAlias

    T = TypeVar("T")


__json_converter = make_converter()
__json_converter.register_structure_hook(ast.AST, lambda _, __: None)
__json_converter.register_unstructure_hook(ast.AST, lambda _: None)


FileName: TypeAlias = str
ModuleName: TypeAlias = str

ImportsIr: TypeAlias = dict[ModuleName, FileIr]


def serialise(model: Any, **kwargs) -> str:
    return __json_converter.dumps(model, **kwargs)


def deserialise(json: str, *, type: type[T], **kwargs) -> T:
    return __json_converter.loads(json, cl=type, **kwargs)


def serialise_irs(
    *,
    target_name: FileName,
    target_ir: FileIr,
    imports_ir: ImportsIr,
) -> str:
    return json.dumps(
        OutputIrs(
            import_ir=imports_ir,
            target_ir={"filename": target_name, "ir": target_ir},
        ),
        indent=4,
        cls=RattrIrEncoder,
    )


def serialise_results_for_output(results: FileResults) -> str:
    """Serialise the results with a a custom encode with ordering, etc."""
    return json.dumps(results, indent=4, cls=RattrResultsEncoder)


class TargetIr(TypedDict):
    filename: FileName
    ir: FileIr


@attrs.frozen
class OutputIrs:
    import_ir: ImportsIr
    target_ir: TargetIr


class RattrIrEncoder(json.JSONEncoder):
    """Return the results IR as JSON."""

    def default(self, obj: object):
        if isinstance(obj, OutputIrs):
            return {
                "import_ir": obj.import_ir,
                "target_ir": obj.target_ir,
            }

        if isinstance(obj, FileIr):
            return {
                "context": obj.context,
                "file_ir": {
                    repr(symbol): self.default(ir)
                    for symbol, ir in obj._file_ir.items()
                },
            }

        if isinstance(obj, Context):
            return {
                "parent": obj.parent,
                "file": obj.file,
                "symbol_table": obj.symbol_table,
            }

        if isinstance(obj, SymbolTable):
            return {identifier: symbol for identifier, symbol in obj._symbols.items()}

        if isinstance(obj, Symbol):
            as_dict = attrs.asdict(obj)
            if as_dict["token"] is not None:
                as_dict["token"] = None
            if as_dict["location"] is not None:
                if as_dict["location"]["token"] is not None:
                    as_dict["location"]["token"] = None
            return as_dict

        if isinstance(obj, Path):
            return str(obj)

        if isinstance(obj, set):
            return sorted(obj)

        if isinstance(obj, list):
            return sorted(set(obj))

        if isinstance(obj, dict):
            return obj

        return super().default(obj)


class RattrResultsEncoder(json.JSONEncoder):
    """Return the results encoded as JSON."""

    def default(self, obj: object):
        if isinstance(obj, FileResults):
            return obj._function_results

        if isinstance(obj, set):
            return sorted(obj)

        if isinstance(obj, list):
            return sorted(set(obj))

        return super().default(obj)
