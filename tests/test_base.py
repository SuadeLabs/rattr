"""Rattr Base class tests."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from rattr.analyser.base import Assertor, CustomFunctionHandler
from rattr.models.symbol import Call, CallArguments, Import, Name

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests.shared import ArgumentsFn, MakeRootContextFn, StateFn


@pytest.fixture(autouse=True)
def __set_current_file(state: StateFn) -> Iterator[None]:
    with state(current_file=Path(__file__)):
        yield


class TestAssertor:
    def test_assertor_is_strict(self, capfd: pytest.CaptureFixture[str]):
        assertor = Assertor(is_strict=True)

        with mock.patch("sys.exit") as _exit:
            assertor.failed("the reason")

        _, stderr = capfd.readouterr()

        assert "the reason" in stderr
        assert _exit.call_count == 1

    def test_assertor_not_is_strict(
        self,
        capfd: pytest.CaptureFixture[str],
        arguments: ArgumentsFn,
    ):
        assertor = Assertor(is_strict=False)

        with arguments(_warning_level="all"):
            with mock.patch("sys.exit") as _exit:
                assertor.failed("the reason2")

        _, stderr = capfd.readouterr()

        assert "the reason" in stderr
        assert _exit.call_count == 0


class TestCustomFunctionHandler:
    def test_register_builtin(self, PrintBuiltinAnalyser):
        handler = CustomFunctionHandler()
        assert len(handler._builtins) == 0

        handler = CustomFunctionHandler([PrintBuiltinAnalyser()], [])
        assert len(handler._builtins) == 1

    def test_register_user_def(self, ExampleFuncAnalyser):
        handler = CustomFunctionHandler()
        assert len(handler._user_def) == 0

        handler = CustomFunctionHandler([], [ExampleFuncAnalyser()])
        assert len(handler._user_def) == 1

    def test_get_with_empty_context(
        self,
        handler: CustomFunctionHandler,
        make_root_context: MakeRootContextFn,
    ):
        context = make_root_context(include_root_symbols=True)

        # From _PrintBuiltinAnalyser, _ExampleFuncAnalyser
        assert handler.get("print", context).name == "print"
        assert handler.get("example", context).name == "example"

        # Has no handler
        assert handler.get("some_non_sense", context) is None

    def test_get_with_populated_context(
        self,
        handler: CustomFunctionHandler,
        make_root_context: MakeRootContextFn,
    ):
        context = make_root_context(
            [
                Import(name="exy", qualified_name="module.example"),
                Import(name="mod", qualified_name="module"),
            ],
            include_root_symbols=True,
        )

        # From _PrintBuiltinAnalyser, _ExampleFuncAnalyser
        assert handler.get("print", context).name == "print"
        assert handler.get("example", context).name == "example"

        # From _ExampleFuncAnalyser
        # In this context we have imported the target of _ExampleFuncAnalyser in two
        # ways, thus we ought to be able to find the custom analyser when using the
        # local name.
        assert handler.get("exy", context).name == "example"
        assert handler.get("mod.example", context).name == "example"

        # Has no handler
        assert handler.get("some_non_sense", context) is None

    def test_has_analyser(
        self,
        handler: CustomFunctionHandler,
        make_root_context: MakeRootContextFn,
    ):
        context = make_root_context(include_root_symbols=True)

        # From _PrintBuiltinAnalyser, _ExampleFuncAnalyser
        assert handler.has_analyser("print", context)
        assert handler.has_analyser("example", context)

        # Has no handler
        assert not handler.has_analyser("wibble", context)
        assert not handler.has_analyser("wibble_wibble", context)

    def test_handle_def(
        self,
        handler: CustomFunctionHandler,
        make_root_context: MakeRootContextFn,
    ):
        context = make_root_context(include_root_symbols=True)
        mock_call = mock.Mock()

        with pytest.raises(ValueError):
            handler.handle_def("wibble", mock_call, context)

        assert handler.handle_def("print", mock_call, context) == {
            "sets": {Name("set_in_print_def")},
            "gets": {Name("get_in_print_def")},
            "dels": {Name("del_in_print_def")},
            "calls": {
                Call(
                    name="call_in_print_def",
                    args=CallArguments(args=(), kwargs={}),
                    target=None,
                ),
            },
        }

        assert handler.handle_def("example", mock_call, context) == {
            "sets": {Name("set_in_example_def")},
            "gets": {Name("get_in_example_def")},
            "dels": {Name("del_in_example_def")},
            "calls": {
                Call(
                    name="call_in_example_def",
                    args=CallArguments(args=(), kwargs={}),
                    target=None,
                ),
            },
        }

    def test_handle_call(
        self,
        handler: CustomFunctionHandler,
        make_root_context: MakeRootContextFn,
    ):
        context = make_root_context(include_root_symbols=True)
        mock_call = mock.Mock()

        with pytest.raises(ValueError):
            handler.handle_call("wibble", mock_call, context)

        assert handler.handle_call("print", mock_call, context) == {
            "sets": {Name("set_in_print")},
            "gets": {Name("get_in_print")},
            "dels": {Name("del_in_print")},
            "calls": {
                Call(
                    name="call_in_print",
                    args=CallArguments(args=(), kwargs={}),
                    target=None,
                ),
            },
        }

        assert handler.handle_call("example", mock_call, context) == {
            "sets": {Name("set_in_example")},
            "gets": {Name("get_in_example")},
            "dels": {Name("del_in_example")},
            "calls": {
                Call(
                    name="call_in_example",
                    args=CallArguments(args=(), kwargs={}),
                    target=None,
                ),
            },
        }
