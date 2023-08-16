from __future__ import annotations

from importlib.util import find_spec

import pytest

from rattr.models.symbol.util import (
    get_basename_from_name,
    get_module_name_and_spec,
    get_possible_module_names,
    with_call_brackets,
    without_call_brackets,
)


class WithCallBrackets:
    def test_the_empty_string(self):
        assert with_call_brackets("") == ""

    def test_no_call_brackets(self):
        assert (
            with_call_brackets("i_dont_have_call_brackets")
            == "i_dont_have_call_brackets()"
        )

    def test_call_brackets(self):
        assert (
            with_call_brackets("keep_my_call_brackets()")
            == "keep_my_call_brackets()"
        )

    def test_just_brackets(self):
        assert with_call_brackets("()") == "()"
        assert with_call_brackets(")(") == ")(()"

    def test_separated_brackets(self):
        assert (
            with_call_brackets("do_not_count(my_brackets)")
            == "do_not_count(my_brackets)()"
        )


class TestWithoutCallBrackets:
    def test_the_empty_string(self):
        assert without_call_brackets("") == ""

    def test_no_call_brackets(self):
        assert (
            without_call_brackets("i_dont_have_call_brackets")
            == "i_dont_have_call_brackets"
        )

    def test_call_brackets(self):
        assert (
            without_call_brackets("remove_my_call_brackets")
            == "remove_my_call_brackets"
        )

    def test_just_brackets(self):
        assert without_call_brackets("()") == ""
        assert without_call_brackets(")(") == ")("

    def test_separated_brackets(self):
        assert (
            without_call_brackets("do_not_remove(my_brackets)")
            == "do_not_remove(my_brackets)"
        )


class TestGetBasenameFromString:
    def test_the_empty_string(self):
        assert get_basename_from_name("") == ""

    def test_is_already_basename(self):
        assert get_basename_from_name("my_var") == "my_var"

    def test_is_dotted(self):
        assert get_basename_from_name("my_var.attr") == "my_var"
        assert get_basename_from_name("my_var.deeply.nested.attrs") == "my_var"

    def test_is_starred(self):
        assert get_basename_from_name("*my_var") == "my_var"

    def test_is_starred_and_dotted(self):
        assert get_basename_from_name("*my_var.attr") == "my_var"
        assert get_basename_from_name("*my_var.deeply.nested.attrs") == "my_var"


class TestGetPossibleModuleNames:
    def test_the_empty_string(self):
        assert get_possible_module_names("") == [""]

    def test_dotted(self):
        assert get_possible_module_names("a.b.c.d") == ["a.b.c.d", "a.b.c", "a.b", "a"]

    def test_not_dotted(self):
        assert get_possible_module_names("non_dotted_name") == ["non_dotted_name"]

    @pytest.mark.parametrize(
        "target,expected",
        [
            ("os.path.join", ["os.path.join", "os.path", "os"]),
            ("pathlib.Path.", ["pathlib.Path", "pathlib"]),
            ("rattr.util.is_name", ["rattr.util.is_name", "rattr.util", "rattr"]),
        ],
        ids=[
            "os.path.join",
            "pathlib.Path.",
            "rattr.util.is_name",
        ],
    )
    def test_real_world(self, target: str, expected: list[str]):
        assert get_possible_module_names(target) == expected


class TestGetModuleNameAndSpec:
    def test_the_empty_string(self):
        assert get_module_name_and_spec("") == (None, None)

    def test_non_existant_module(self):
        assert get_module_name_and_spec("i.am.not.a.module") == (None, None)

    @pytest.mark.parametrize(
        "target,module_name",
        [
            # stdlib
            ("math", "math"),
            ("math.pi", "math"),
            ("os", "os"),
            ("os.path", "os.path"),
            # internal
            ("rattr.analyser", "rattr.analyser"),
            ("rattr.analyser.util.get_module_spec", "rattr.analyser.util"),
        ],
    )
    def test_real_world(self, target: str, module_name: str):
        assert get_module_name_and_spec(target) == (module_name, find_spec(module_name))
