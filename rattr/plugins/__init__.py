from dataclasses import dataclass
from typing import List, Set, Union

from rattr.analyser.base import (
    Assertor,
    CustomFunctionAnalyser,
    CustomFunctionHandler,
)
from rattr.analyser.util import MODULE_BLACKLIST_PATTERNS
from rattr.plugins.analysers import DEFAULT_FUNCTION_ANALYSERS as DEFAULTS

Plugin = Union[Assertor, CustomFunctionAnalyser]


@dataclass
class Plugins:
    assertors: List[Assertor]
    analysers: List[CustomFunctionAnalyser]

    _handler: CustomFunctionHandler = None

    @property
    def custom_function_handler(self) -> CustomFunctionHandler:
        if self._handler is None:
            self._handler = CustomFunctionHandler(DEFAULTS, self.analysers)

        return self._handler

    def register(self, plugin: Plugin) -> None:
        """Register the given plugin."""
        if isinstance(plugin, Assertor):
            return self.assertors.append(plugin)

        if isinstance(plugin, CustomFunctionAnalyser):
            return self.analysers.append(plugin)

        raise TypeError

    def blacklist(self, module_or_modules: Union[str, Set[str]]) -> None:
        """Add the given module pattern to the module blacklist."""
        if not isinstance(module_or_modules, (str, set)):
            raise TypeError

        if isinstance(module_or_modules, str):
            modules = {
                module_or_modules,
            }

        if isinstance(module_or_modules, set):
            modules = module_or_modules

        for module in modules:
            MODULE_BLACKLIST_PATTERNS.add(module)


plugins = Plugins(list(), list())
