from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from rattr.models.results import FileResults
from rattr.results import (
    IrCallTreeNode,
    IrEnvironment,
    IrTarget,
    construct_call_swaps,
    find_call_target_and_ir,
    unbind_ir_with_call_swaps,
)

if TYPE_CHECKING:
    from rattr.analyser.types import ImportIrs
    from rattr.models.ir import FileIr, FunctionIr
    from rattr.models.symbol import Call


def generate_results_from_ir(
    *,
    target_ir: FileIr,
    import_irs: ImportIrs,
) -> FileResults:
    results = FileResults()
    environment = IrEnvironment(target_ir=target_ir, import_irs=import_irs)

    for symbol, ir in target_ir.items():
        target = IrTarget(symbol=symbol, ir=ir)

        ir_call_tree = make_target_ir_call_tree(target, environment=environment)
        simplified = destructively_simplify_ir_call_tree(ir_call_tree)

        results[symbol.id] = {
            "gets": {s.id for s in simplified["gets"]},
            "sets": {s.id for s in simplified["sets"]},
            "dels": {s.id for s in simplified["dels"]},
            "calls": {s.name_of_call for s in simplified["calls"]},
        }

    return results


def make_target_ir_call_tree(
    target: IrTarget,
    *,
    environment: IrEnvironment,
) -> IrCallTreeNode:
    """Return the constructed IR call tree stemming from the given target.

    Implementation:
        BFS the call tree from the root, constructing the nodes and children along the
        way.

    Infinite tree depth on recursion:
        A call tree may be of infinite depth due to direct or indirect recursion.
        However, if any call that has been seen before with the same parameters can be
        ignored then we can know that the finite tree with the recursive calls visited
        only once is equivalent. This assumption is proven below.

    Recursion removal proof:

        Given that:
            R(A) is the final result of a A
            for any target A

            r(A, P) is the partial result of A when called with params P
            for any target A and any parameter spec P

            R_a ∪ R_b = {k: R_a[k] ∪ R_b[k] | k ∈ {"gets", "sets", "dels", "calls"}}
            for any results R_a, R_b

            R_a ∪ R_a = R_a by the definition of ∪ over results
            for any results R_a

        Direct recursion:
            A -> A

            R(A)    = r(A, P_)
            .       ∪ r(A, P_A) ∪ r(A, P_A) ∪ ... ∪ r(A, P_A)       (by definition)
            R(A)    = r(A)
            .       ∪ r(A, P_A)                                     (idempotent)

            where P_ is the initial call's parameter spec
            and   P_A is the parameter spec for the recursive call to A made in A

        Indirect recursion:
            A -> B -> ... -> Z -> A

            R(A)    = [r(A, P_)  ∪ r(B, P_A) ∪ ... ∪ r(Z, P_Y)]
            .       ∪ [r(A, P_Z) ∪ r(B, P_A) ∪ ... ∪ r(Z, P_Y)]
            .       ...
            .       ∪ [r(A, P_Z) ∪ r(B, P_A) ∪ ... ∪ r(Z, P_Y)]     (by definition)

            R(A)    = r(A, P_)
                    ∪ [r(A, P_Z) ∪ r(B, P_A) ∪ ... ∪ r(Z, P_Y)]     (idempotent)

            where P_ is the initial call's parameter spec
            and   P_N is the parameter spec for a call as seen in target N

        There are more complex cases (direct recursion where A calls out to other
        functions, the same for each step in the case of indirect recursion, etc),
        however, those trivially hold given the above and are cumbersome to express.
    """
    root = IrCallTreeNode.new(target=target, call=None)

    queue = deque([root])
    seen: set[Call] = set()

    while queue:
        node = queue.popleft()

        for call in node.edges_out:
            if call.symbol in seen:
                continue

            call_target = find_call_target_and_ir(call, environment=environment)

            if call_target is None:
                continue

            child = IrCallTreeNode.new(target=call_target, call=call)

            node.children.append(child)
            queue.append(child)

            seen.add(call.symbol)

    return root


def destructively_simplify_ir_call_tree(root: IrCallTreeNode) -> FunctionIr:
    queue = post_order_traversal_queue(root)

    while queue:
        node = queue.popleft()

        if not node.children:
            # Leaves are already simplified
            continue

        for child in node.children:
            swaps = construct_call_swaps(child.target.symbol, child.edge_in.symbol)
            unbound = unbind_ir_with_call_swaps(child.target.ir, swaps)

            node.target.ir["sets"] |= unbound["sets"]
            node.target.ir["gets"] |= unbound["gets"]
            node.target.ir["dels"] |= unbound["dels"]

    return root.target.ir


def post_order_traversal_queue(root: IrCallTreeNode) -> deque[IrCallTreeNode]:
    queue = deque([root])
    pre_order_queue = list()

    while queue:
        node = queue.popleft()
        for child in node.children:
            queue.append(child)
        pre_order_queue.append(node)

    return deque(pre_order_queue[::-1])
