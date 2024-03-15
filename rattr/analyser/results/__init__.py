from __future__ import annotations

# isort: off
from rattr.analyser.results._types import (
    IrCall,
    IrCallTreeNode,
    IrEnvironment,
    IrTarget,
)

# isort: on
from rattr.analyser.results._find_call_target import find_call_target_and_ir
from rattr.analyser.results._simplify_utils import (
    construct_call_swaps,
    unbind_ir_with_call_swaps,
    unbind_name,
)
from rattr.analyser.results.util import (
    destructively_simplify_ir_call_tree,
    generate_results_from_ir,
    make_target_ir_call_tree,
)

__all__ = [
    "IrCall",
    "IrCallTreeNode",
    "IrEnvironment",
    "IrTarget",
    "find_call_target_and_ir",
    "construct_call_swaps",
    "unbind_ir_with_call_swaps",
    "unbind_name",
    "destructively_simplify_ir_call_tree",
    "generate_results_from_ir",
    "make_target_ir_call_tree",
]
