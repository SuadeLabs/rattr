from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from rattr.analyser.util import read

if TYPE_CHECKING:
    from typing import Callable


here = Path(__file__).resolve().parent


@pytest.fixture
def get_test_file() -> Callable[[str], Path]:
    def __file_getter(name: str):
        the_file = here / "data" / name
        assert the_file.exists(), f"{str(the_file)} does not exist"
        return the_file

    return __file_getter


@pytest.fixture
def get_non_existent_file() -> Callable[[str], Path]:
    def __file_getter(name: str):
        the_file = here / "data" / name
        assert not the_file.exists(), f"{str(the_file)} exists"
        return the_file

    return __file_getter


class TestRead:
    @pytest.mark.parametrize(
        "filename",
        ["the_empty_file.py", "only_blank_lines.py", "a_populated_file.py"],
    )
    def test_file(self, get_test_file, filename):
        the_file: Path = get_test_file(filename)

        with read(the_file) as (number_of_lines, content):
            assert content == the_file.read_text()
            assert number_of_lines == len(the_file.read_text().splitlines()) + 1

    @pytest.mark.parametrize("filename", ["foo.py"])
    def test_non_existent_file(self, get_non_existent_file, filename):
        with pytest.raises(FileNotFoundError):
            with read(get_non_existent_file(filename)) as _:
                ...
