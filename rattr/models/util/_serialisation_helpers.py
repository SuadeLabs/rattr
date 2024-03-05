from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import attrs
from cattrs.gen import make_dict_structure_fn, make_dict_unstructure_fn, override
from cattrs.preconf.json import make_converter

from rattr.models.context import Context, SymbolTable
from rattr.models.ir import FileIr, FunctionIr
from rattr.models.results import FileResults, FunctionName, FunctionResults
from rattr.models.symbol import (
    AnyCallInterface,
    Builtin,
    Call,
    CallInterface,
    Class,
    Func,
    Import,
    Location,
    Name,
    Symbol,
)

if TYPE_CHECKING:
    from typing import Any, Final, Literal

    from cattrs.converters import Converter

    from rattr.ast.types import Identifier


__symbols: Final = (Name, Builtin, Import, Func, Class, Call)
__name_to_symbol: Final = {symbol.__name__: symbol for symbol in __symbols}


def make_json_converter() -> Converter:
    converter = make_converter()

    converter.register_structure_hook(
        Location,
        make_dict_structure_fn(
            Location,
            converter,
            _cattrs_use_alias=True,
            token=override(omit=True),
        ),
    )
    converter.register_unstructure_hook(
        Location,
        make_dict_unstructure_fn(
            Location,
            converter,
            _cattrs_use_alias=True,
            token=override(omit=True),
        ),
    )

    call_interface_converter = make_converter()
    converter.register_structure_hook(
        CallInterface,
        make_call_interface_deserialiser(call_interface_converter),
    )
    converter.register_unstructure_hook(
        CallInterface,
        make_call_interface_serialiser(call_interface_converter),
    )
    converter.register_structure_hook(
        AnyCallInterface,
        make_call_interface_deserialiser(call_interface_converter),
    )
    converter.register_unstructure_hook(
        AnyCallInterface,
        make_call_interface_serialiser(call_interface_converter),
    )

    symbol_converter = make_symbol_json_converter()
    converter.register_structure_hook(
        Symbol,
        make_symbol_deserialiser(symbol_converter),
    )
    converter.register_unstructure_hook(
        Symbol,
        make_symbol_serialiser(symbol_converter),
    )

    converter.register_structure_hook(
        SymbolTable,
        make_symbol_table_deserialiser(converter),
    )
    converter.register_unstructure_hook(
        SymbolTable,
        make_symbol_table_serialiser(converter),
    )

    converter.register_structure_hook(
        Context,
        make_dict_structure_fn(
            Context,
            converter,
            _cattrs_use_alias=True,
            _cattrs_include_init_false=True,
        ),
    )
    converter.register_unstructure_hook(
        Context,
        make_dict_unstructure_fn(
            Context,
            converter,
            _cattrs_use_alias=True,
            _cattrs_include_init_false=True,
        ),
    )

    converter.register_structure_hook(
        FileResults,
        make_file_results_deserialiser(converter),
    )
    converter.register_unstructure_hook(
        FileResults,
        make_file_results_serialiser(converter),
    )

    converter.register_structure_hook(FileIr, make_file_ir_deserialiser(converter))
    converter.register_unstructure_hook(FileIr, make_file_ir_serialiser(converter))

    return converter


def make_symbol_json_converter() -> Converter:
    converter = make_converter()

    converter.register_structure_hook(
        Location,
        make_dict_structure_fn(
            Location,
            converter,
            _cattrs_use_alias=True,
            token=override(omit=True),
        ),
    )
    converter.register_unstructure_hook(
        Location,
        make_dict_unstructure_fn(
            Location,
            converter,
            _cattrs_use_alias=True,
            token=override(omit=True),
        ),
    )

    call_interface_converter = make_converter()
    converter.register_structure_hook(
        CallInterface,
        make_call_interface_deserialiser(call_interface_converter),
    )
    converter.register_unstructure_hook(
        CallInterface,
        make_call_interface_serialiser(call_interface_converter),
    )
    converter.register_structure_hook(
        AnyCallInterface,
        make_call_interface_deserialiser(call_interface_converter),
    )
    converter.register_unstructure_hook(
        AnyCallInterface,
        make_call_interface_serialiser(call_interface_converter),
    )

    converter.register_structure_hook(ast.AST, lambda _, __: None)
    converter.register_unstructure_hook(ast.AST, lambda _: None)

    return converter


def make_symbol_serialiser(converter: Converter):
    def serialise_symbol(symbol: Symbol) -> dict[str, Any]:
        data: dict[str, Any] = converter.unstructure(symbol)
        data.pop("token", None)  # not serialisable, should be None form raw converter
        data = {"type": symbol.__class__.__name__, **data}

        if isinstance(symbol, Call) and data["target"] is not None:
            data["target"] = serialise_symbol(symbol.target)

        return data

    return serialise_symbol


def make_symbol_deserialiser(converter: Converter):
    def deserialise_symbol(data: dict[str, Any], _: type[Symbol]) -> Symbol:
        type: str = data.pop("type", None)

        if type is None:
            raise ValueError("missing type")

        if type not in __name_to_symbol.keys():
            raise ValueError(f"invalid type: {type}")

        if type == Call.__name__:
            target_data = data.pop("target", None)

            if target_data is not None:
                target = deserialise_symbol(target_data, _)
            else:
                target = None

            data["target"] = None
            symbol = converter.structure(data, __name_to_symbol[type])

            return attrs.evolve(symbol, target=target)

        return converter.structure(data, __name_to_symbol[type])

    return deserialise_symbol


def make_call_interface_serialiser(converter: Converter):
    def serialise_call_interface(
        call_interface: CallInterface,
    ) -> dict[str, Any] | Literal["any"]:
        if isinstance(call_interface, AnyCallInterface):
            return "any"
        else:
            return converter.unstructure(call_interface)

    return serialise_call_interface


def make_call_interface_deserialiser(converter: Converter):
    def deserialise_call_interface(
        data: dict[str, Any] | Literal["any"] | object,
        type: type[CallInterface],
    ) -> CallInterface:
        if data == "any":
            return AnyCallInterface()
        elif isinstance(data, dict):
            return converter.structure(data, CallInterface)
        else:
            raise ValueError(f"not a valid call interface: {data}")

    return deserialise_call_interface


def make_symbol_table_serialiser(converter: Converter):
    def serialise_symbol_table(symbol_table: SymbolTable) -> dict[str, Any]:
        return converter.unstructure(symbol_table._symbols)

    return serialise_symbol_table


def make_symbol_table_deserialiser(converter: Converter):
    def deserialise_symbol_table(
        data: dict[Identifier | object, dict[str, Any] | object],
        cls: type[SymbolTable],
    ) -> SymbolTable:
        symbol_table = cls()
        symbol_table._symbols = converter.structure(data, dict[str, Symbol])
        return symbol_table

    return deserialise_symbol_table


def make_file_results_serialiser(_: Converter):
    def serialise_file_results(file_results: FileResults) -> dict[str, FunctionResults]:
        return {
            name: {
                "gets": sorted(file_results._function_results[name]["gets"]),
                "sets": sorted(file_results._function_results[name]["sets"]),
                "dels": sorted(file_results._function_results[name]["dels"]),
                "calls": sorted(file_results._function_results[name]["calls"]),
            }
            for name in sorted(file_results._function_results.keys())
        }

    return serialise_file_results


def make_file_results_deserialiser(converter: Converter):
    def deserialise_file_results(
        data: dict[Identifier | object, dict[str, Any] | object],
        cls: type[FileResults],
    ) -> FileResults:
        return cls(converter.structure(data, dict[FunctionName, FunctionResults]))

    return deserialise_file_results


def make_file_ir_serialiser(converter: Converter):
    def serialise_file_ir(file_ir: FileIr) -> dict[str, Any]:
        return {
            "context": converter.unstructure(file_ir.context),
            "symbols": {
                symbol.id: converter.unstructure(symbol)
                for symbol in sorted(file_ir._file_ir.keys())
            },
            "function_irs": {
                symbol.id: {
                    "gets": sorted(
                        converter.unstructure(file_ir._file_ir[symbol]["gets"]),
                        key=lambda s: s["name"],
                    ),
                    "sets": sorted(
                        converter.unstructure(file_ir._file_ir[symbol]["sets"]),
                        key=lambda s: s["name"],
                    ),
                    "dels": sorted(
                        converter.unstructure(file_ir._file_ir[symbol]["dels"]),
                        key=lambda s: s["name"],
                    ),
                    "calls": sorted(
                        converter.unstructure(file_ir._file_ir[symbol]["calls"]),
                        key=lambda s: s["name"],
                    ),
                }
                for symbol in sorted(file_ir._file_ir.keys())
            },
        }

    return serialise_file_ir


def make_file_ir_deserialiser(converter: Converter):
    def deserialise_file_ir(data: dict[str, Any], cls: type[FileIr]) -> FileIr:
        context_data: dict[str, Any] = data.get("context", None)
        context = (
            converter.structure(context_data, Context)
            if context_data is not None
            else None
        )

        symbols_data: dict[Identifier, dict[str, Any]] = data.get("symbols", None)
        fn_irs_data: dict[Identifier, dict[str, Any]] = data.get("function_irs", None)

        if symbols_data is None or fn_irs_data is None:
            raise ValueError

        symbols = {
            identifier: converter.structure(symbol_data, Symbol)
            for identifier, symbol_data in symbols_data.items()
        }
        fn_irs = {
            identifier: converter.structure(ir_data, FunctionIr)
            for identifier, ir_data in fn_irs_data.items()
        }

        return cls(
            context=context,
            file_ir={
                symbol: value
                for name, symbol in symbols.items()
                if (value := fn_irs.get(name, None)) is not None
            },
        )

    return deserialise_file_ir
