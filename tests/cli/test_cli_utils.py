from __future__ import annotations

from rattr.cli._util import get_type_name


class TestUtils:
    def test_get_type_name(self):
        assert get_type_name(None) == "NoneType"

        assert get_type_name(True) == "bool"
        assert get_type_name(1) == "int"
        assert get_type_name(1.0) == "float"

        assert get_type_name([1]) == "list[int]"
        assert get_type_name(["1"]) == "list[str]"
        assert get_type_name(["1", 2]) == "list[int | str]"

        assert get_type_name({"1": 1, "2": 2}) == "dict[str, int]"
        assert get_type_name({"1": 1, "2": "two"}) == "dict[str, int | str]"
