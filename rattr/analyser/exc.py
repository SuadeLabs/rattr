from __future__ import annotations


class RattrResultsError(Exception):
    def __init__(self, message: str = "invalid rattr results") -> None:
        self.message = message
        super().__init__(message)
