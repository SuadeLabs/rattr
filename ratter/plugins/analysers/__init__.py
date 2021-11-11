from ratter.plugins.analysers.builtins import (
    GetattrAnalyser,
    SetattrAnalyser,
    HasattrAnalyser,
    DelattrAnalyser,
)


BUILTIN_FUNCTION_ANALYSERS = (
    GetattrAnalyser(),
    SetattrAnalyser(),
    HasattrAnalyser(),
    DelattrAnalyser(),
)
