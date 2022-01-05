from ratter.plugins.analysers.builtins import (
    DelattrAnalyser,
    GetattrAnalyser,
    HasattrAnalyser,
    SetattrAnalyser,
    SortedAnalyser,
)

BUILTIN_FUNCTION_ANALYSERS = (
    GetattrAnalyser(),
    SetattrAnalyser(),
    HasattrAnalyser(),
    DelattrAnalyser(),
    SortedAnalyser(),
)
