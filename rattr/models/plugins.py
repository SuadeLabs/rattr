from __future__ import annotations

import attrs

from rattr.analyser.base import Assertor, CustomFunctionAnalyser, CustomFunctionHandler
from rattr.config import Config


@attrs.mutable
class Plugins:
    assertors: list[Assertor]
    analysers: list[CustomFunctionAnalyser]

    _handler: CustomFunctionHandler = None

    @property
    def custom_function_handler(self) -> CustomFunctionHandler:
        from rattr.plugins.analysers import DEFAULT_FUNCTION_ANALYSERS

        if self._handler is None:
            self._handler = CustomFunctionHandler(
                builtins=DEFAULT_FUNCTION_ANALYSERS,
                user_defined=self.analysers,
            )

        return self._handler

    def register(self, plugin: Assertor | CustomFunctionAnalyser) -> None:
        """Register the given plugin."""
        if isinstance(plugin, Assertor):
            return self.assertors.append(plugin)

        if isinstance(plugin, CustomFunctionAnalyser):
            return self.analysers.append(plugin)

        raise TypeError

    def blacklist(self, module_or_modules: str | set[str]) -> None:
        """Add the given module pattern to the module blacklist."""
        config = Config()

        if not isinstance(module_or_modules, (str, set)):
            raise TypeError

        if isinstance(module_or_modules, str):
            modules = {
                module_or_modules,
            }

        if isinstance(module_or_modules, set):
            modules = module_or_modules

        for module in modules:
            config.PLUGIN_BLACKLIST_PATTERNS.add(module)
