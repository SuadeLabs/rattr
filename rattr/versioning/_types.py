from __future__ import annotations

import ast


class AstNodeNotInPythonVersion(ast.expr):
    """Represent a type that is not present in this python version."""
