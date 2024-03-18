from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from rattr.analyser.types import ImportIrs
    from rattr.models.ir import FileIr, FunctionIr
    from rattr.models.symbol import Call, Class, Func


class IrTarget(NamedTuple):
    symbol: Func | Class
    ir: FunctionIr


class IrCall(NamedTuple):
    caller: Func | Class
    symbol: Call


class IrEnvironment(NamedTuple):
    target_ir: FileIr
    import_irs: ImportIrs


class IrCallTreeNode(NamedTuple):
    target: IrTarget

    edge_in: IrCall | None
    edges_out: list[IrCall]

    children: list[IrCallTreeNode]

    @classmethod
    def new(cls, target: IrTarget, call: IrCall | None) -> IrCallTreeNode:
        return cls(
            target=IrTarget(symbol=target.symbol, ir=target.ir.copy()),
            edge_in=call,
            edges_out=[
                IrCall(caller=target.symbol, symbol=symbol)
                for symbol in sorted(target.ir["calls"], key=lambda c: c.id)
            ],
            children=[],
        )
