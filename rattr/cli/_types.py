from __future__ import annotations

from enum import Enum


class TomlArgumentType(Enum):
    flag = "bool"
    """I.e. a boolean flag.

    In toml:
        variable=true

    In sys argument list:
        --variable
    """

    int = "int"
    """I.e. a single int value.

    In toml:
        variable=42

    In sys argument list:
        --variable 42
    """

    string = "str"
    """I.e. a single string value.

    In toml:
        variable="some value"

    In sys argument list:
        --variable "some value"
    """

    list_of_strings = "list[str]"
    """I.e. a list of values.

    In toml:
        variable=["value", "another value", "etc"]

    In sys argument list:
        --variable "value" --variable "another value" --variable "etc"
    """

    def __str__(self) -> str:
        return self.value

    def is_valid(self, value: bool | int | str | list[str]) -> bool:
        if self == TomlArgumentType.flag:
            return isinstance(value, bool)

        if self == TomlArgumentType.int:
            return isinstance(value, int)

        if self == TomlArgumentType.string:
            return isinstance(value, str)

        if self == TomlArgumentType.list_of_strings:
            return isinstance(value, list) and all(isinstance(_v, str) for _v in value)

        raise NotImplementedError
