from __future__ import annotations

import argparse
import sys as _sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import NoReturn


class ArgumentParser(argparse.ArgumentParser):
    def exit(self, status: int = 0, message: str | None = None) -> NoReturn | None:
        if not self.exit_on_error:
            raise argparse.ArgumentError(None, message or "")

        if message:
            self._print_message(message, _sys.stderr)

        if self.exit_on_error:
            _sys.exit(status)
