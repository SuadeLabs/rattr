from __future__ import annotations

import ast
from pathlib import Path

import attrs
import pytest

from rattr.models.symbol import (
    AnyCallInterface,
    CallArguments,
    CallInterface,
    Location,
    Symbol,
)


@attrs.frozen
class _DerivedSymbol(Symbol):
    """Symbol for generic tests."""

    pass


class TestSymbol:
    def test_unable_to_directly_initialise(self):
        with pytest.raises(NotImplementedError):
            Symbol("blah")

    def test_able_to_initialise_sub_classed(self):
        assert _DerivedSymbol(name="blah")


class TestCallInterface:
    def test_all(self):
        interface = CallInterface(
            posonlyargs=["a", "b"],
            args=["arg", "another_arg"],
            kwonlyargs=["kwonly_1", "another_kwonly"],
        )
        assert interface.all == (
            "a",
            "b",
            "arg",
            "another_arg",
            "kwonly_1",
            "another_kwonly",
        )

    def test_all_with_vararg_and_kwarg(self):
        interface = CallInterface(
            posonlyargs=["a", "b"],
            args=["arg", "another_arg"],
            vararg="vararg",
            kwonlyargs=["kwonly_1", "another_kwonly"],
            kwarg="kwarg",
        )
        assert interface.all == (
            "a",
            "b",
            "arg",
            "another_arg",
            "vararg",
            "kwonly_1",
            "another_kwonly",
            "kwarg",
        )

    def test_from_fn_def(self, parse):
        fn = parse(
            """
            def fn(a, b, /, c, d=None, *, e):
                pass
            """
        ).body[0]

        assert CallInterface.from_fn_def(fn) == CallInterface(
            posonlyargs=["a", "b"],
            args=["c", "d"],
            kwonlyargs=["e"],
        )

    def test_from_fn_def_with_vararg_and_kwarg(self, parse):
        fn = parse(
            """
            def fn(a, b, /, c, d=None, *e, f=1, g=2, **h):
                pass
            """
        ).body[0]

        assert CallInterface.from_fn_def(fn) == CallInterface(
            posonlyargs=["a", "b"],
            args=["c", "d"],
            vararg="e",
            kwonlyargs=["f", "g"],
            kwarg="h",
        )

    def test_is_hashable(self):
        assert isinstance(hash(CallInterface()), int)


class TestAnyCallInterface:
    def test_from_fn_def(self):
        with pytest.raises(NotImplementedError):
            AnyCallInterface.from_fn_def(ast.parse("def f(): pass").body[0])

    def test_is_hashable(self):
        assert isinstance(hash(AnyCallInterface()), int)


class TestCallArguments:
    def test_from_call(self):
        _ast = ast.parse("my_func(a, b, c=var)")

        actual = CallArguments.from_call(_ast.body[0].value)
        expected = CallArguments(args=["a", "b"], kwargs={"c": "var"})

        assert actual == expected

    def test_from_call_with_self(self):
        _ast = ast.parse("obj.my_func(a, b, c=var)")

        actual = CallArguments.from_call(_ast.body[0].value, self="self")
        expected = CallArguments(args=["self", "a", "b"], kwargs={"c": "var"})

        assert actual == expected

    def test_is_hashable(self):
        call_arguments = CallArguments(args=["a", "b"], kwargs={"c": "the_real_c"})
        assert isinstance(hash(call_arguments), int)


class TestLocation:
    @pytest.fixture
    def file(self) -> Path:
        return Path("cwd/my_file.py")

    @pytest.fixture
    def required_kwargs(self) -> dict[str, int | None]:
        return {
            "lineno": 0,
            "end_lineno": None,
            "col_offset": 1,
            "end_col_offset": None,
        }

    def test_not_in_file(self, state, required_kwargs):
        with state(current_file=None):
            with pytest.raises(ValueError):
                Location(**required_kwargs)

    def test_with_derived_location(self, state, file, required_kwargs):
        with state(current_file=file):
            assert Location(**required_kwargs).defined_in == file

    def test_with_explicit_location(self, state, file, required_kwargs):
        # This is not the intended interface, but should no break
        with state(current_file=file):
            assert Location(**required_kwargs, file=file).defined_in == file

    def test_is_hashable(self, required_kwargs):
        assert isinstance(hash(Location(**required_kwargs)), int)
