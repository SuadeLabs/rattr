from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests.shared import StateFn


@pytest.fixture()
def test_file() -> Path:
    return Path("test.py")


@pytest.fixture(autouse=True)
def __set_current_file(state: StateFn, test_file: Path) -> Iterator[None]:
    # Many symbols automatically derive a location
    # The derivation will error if the state's file is not set
    # Se just set it universally for all symbol tests.
    with state(current_file=test_file):
        yield
