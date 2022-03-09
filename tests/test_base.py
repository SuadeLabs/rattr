"""Rattr Base class tests."""

from unittest import mock

import pytest

from rattr.analyser.base import (  # CustomFunctionAnalyser,
    Assertor,
    CustomFunctionHandler,
)
from rattr.analyser.context.symbol import Call, Import, Name


class TestAssertor:
    def test_assertor_is_strict(self, capfd):
        assertor = Assertor(is_strict=True)

        with mock.patch("sys.exit") as _exit:
            assertor.failed("the reason")

        output, _ = capfd.readouterr()

        assert "the reason" in output
        assert _exit.call_count == 1

    def test_assertor_not_is_strict(self, capfd):
        assertor = Assertor(is_strict=False)

        with mock.patch("sys.exit") as _exit:
            assertor.failed("the reason")

        output, _ = capfd.readouterr()

        assert "the reason" in output
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

    def test_get(self, handler: CustomFunctionHandler):
        ctx = mock.Mock()
        ctx.is_import.return_value = True
        ctx.symbol_table.symbols.return_value = []

        assert handler.get("print", ctx).name == "print"
        assert handler.get("example", ctx).name == "example"

        assert handler.get("some_non_sense", ctx) is None

        ctx.symbol_table.symbols.return_value = [
            Import("exy", "module.example"),
            Import("mod", "module"),
        ]

        assert handler.get("exy", ctx).name == "example"
        assert handler.get("mod.example", ctx).name == "example"

        assert handler.get("some_non_sense", ctx) is None

    def test_has_analyser(self, handler: CustomFunctionHandler):
        ctx = mock.Mock()
        ctx.is_import.return_value = True
        ctx.symbol_table.symbols.return_value = []

        assert handler.has_analyser("print", ctx)
        assert handler.has_analyser("example", ctx)

        assert not handler.has_analyser("wibble", ctx)
        assert not handler.has_analyser("wibble_wibble", ctx)

    def test_handle_def(self, handler: CustomFunctionHandler):
        ctx = mock.Mock()
        ctx.is_import.return_value = True
        ctx.symbol_table.symbols.return_value = []

        call = mock.Mock()

        with pytest.raises(ValueError):
            handler.handle_def("wibble", call, ctx)

        assert handler.handle_def("print", call, ctx) == {
            "sets": {
                Name("set_in_print_def"),
            },
            "gets": {
                Name("get_in_print_def"),
            },
            "dels": {
                Name("del_in_print_def"),
            },
            "calls": {
                Call("call_in_print_def", [], {}, None),
            },
        }

        assert handler.handle_def("example", call, ctx) == {
            "sets": {
                Name("set_in_example_def"),
            },
            "gets": {
                Name("get_in_example_def"),
            },
            "dels": {
                Name("del_in_example_def"),
            },
            "calls": {
                Call("call_in_example_def", [], {}, None),
            },
        }

    def test_handle_call(self, handler: CustomFunctionHandler):
        ctx = mock.Mock()
        ctx.is_import.return_value = True
        ctx.symbol_table.symbols.return_value = []

        call = mock.Mock()

        with pytest.raises(ValueError):
            handler.handle_call("wibble", call, ctx)

        assert handler.handle_call("print", call, ctx) == {
            "sets": {
                Name("set_in_print"),
            },
            "gets": {
                Name("get_in_print"),
            },
            "dels": {
                Name("del_in_print"),
            },
            "calls": {
                Call("call_in_print", [], {}, None),
            },
        }

        assert handler.handle_call("example", call, ctx) == {
            "sets": {
                Name("set_in_example"),
            },
            "gets": {
                Name("get_in_example"),
            },
            "dels": {
                Name("del_in_example"),
            },
            "calls": {
                Call("call_in_example", [], {}, None),
            },
        }
