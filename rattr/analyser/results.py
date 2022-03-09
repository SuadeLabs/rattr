"""Rattr functions for producing and displaying results."""
import json

from rattr.analyser.context import Symbol
from rattr.analyser.ir_dag import IrDagNode
from rattr.analyser.types import FileIR, FileResults, ImportsIR


class ResultsEncoder(json.JSONEncoder):
    """Return the results encoded as JSON."""

    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)

        if isinstance(obj, Symbol):
            return repr(obj)

        return super().default(obj)


def generate_results_from_ir(file_ir: FileIR, imports_ir: ImportsIR) -> FileResults:
    """Generate the final results from the given IR.

    Removing cycles:

        Direct recursion:
            A -> A

            R(A)    = r(A) ∪ r(A)                               (by definition)
            .       = r(A)                                      (idempotent)

            where R(A) is the final result of a A;
            .     r(A) is the partial result of A

        Indirect recursion:
            A -> B -> ... -> C -> A

            R(A)    =  r(A)         ∪ r(B) ∪ ... ∪ r(C) ∪ r(A)  (by definition)
            .       = (r(A) ∪ r(A)) ∪ r(B) ∪ ... ∪ r(C)         (commutativity)
            .       =  r(A)         ∪ r(B) ∪ ... ∪ r(C)         (idempotent)

            where R(N) is the final result of a N, for any node N;
            .     r(N) is the partial result of N, for any node N

        I.e. cycles in the DAG of function calls from from root function can be
        simplified by "ignoring" previously visited functions, given the
        arguments are the same (as visiting them a second time will not affect
        the final result).

    """
    simplified: FileResults = dict()

    for foc, foc_ir in file_ir.items():
        ir_dag = IrDagNode(None, foc, foc_ir, file_ir, imports_ir)
        ir_dag.populate()

        composed_ir = ir_dag.simplify()

        simplified[foc.name] = {
            "sets": {s.name for s in composed_ir["sets"]},
            "gets": {s.name for s in composed_ir["gets"]},
            "dels": {s.name for s in composed_ir["dels"]},
            "calls": {s.name for s in composed_ir["calls"]},
        }

    return simplified
