from __future__ import annotations


class RattrUnsupportedError(Exception):
    """Language feature is unsupported by rattr."""

    pass


class RattrUnaryOpInNameable(TypeError):
    """Unary operation found when resolving name."""

    pass


class RattrBinOpInNameable(TypeError):
    """Binary operation found when resolving name."""

    pass


class RattrConstantInNameable(TypeError):
    """Constant found when resolving name."""

    pass


class RattrLiteralInNameable(TypeError):
    """Literal found when resolving name."""

    pass


class RattrComprehensionInNameable(TypeError):
    """Comprehension found when resolving name."""

    pass
