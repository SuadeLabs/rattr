from rattr.plugins.analysers.builtins import (
    DelattrAnalyser,
    GetattrAnalyser,
    HasattrAnalyser,
    SetattrAnalyser,
    SortedAnalyser,
)
from rattr.plugins.analysers.collections import DefaultDictAnalyser

DEFAULT_FUNCTION_ANALYSERS = (
    GetattrAnalyser(),
    SetattrAnalyser(),
    HasattrAnalyser(),
    DelattrAnalyser(),
    SortedAnalyser(),
    DefaultDictAnalyser(),
)
