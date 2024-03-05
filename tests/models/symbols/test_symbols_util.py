from __future__ import annotations

from rattr.models.symbol.util import (
    get_basename_from_name,
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
            with_call_brackets("keep_my_call_brackets_please()")
            == "keep_my_call_brackets_please()"
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
