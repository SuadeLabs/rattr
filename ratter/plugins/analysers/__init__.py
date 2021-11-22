from ratter.plugins.analysers.builtins import (
    DelattrAnalyser,
    GetattrAnalyser,
    HasattrAnalyser,
    SetattrAnalyser
)

BUILTIN_FUNCTION_ANALYSERS = (
    GetattrAnalyser(),
    SetattrAnalyser(),
    HasattrAnalyser(),
    DelattrAnalyser(),
)
