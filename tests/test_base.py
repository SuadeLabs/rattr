"""Rattr Base class tests."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from rattr.analyser.base import Assertor, CustomFunctionAnalyser
from rattr.models.symbol import Call, CallArguments, Name

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests.shared import ArgumentsFn, StateFn


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


def test_custom_function_analyser_on_def(
    builtin_print_analyser: CustomFunctionAnalyser,
    example_func_analyser: CustomFunctionAnalyser,
):
    mock_call = mock.Mock()
    mock_context = mock.Mock()

    assert builtin_print_analyser.on_def("print", mock_call, mock_context) == {
        "gets": {Name("get_in_print_def")},
        "sets": {Name("set_in_print_def")},
        "dels": {Name("del_in_print_def")},
        "calls": {
            Call(
                name="call_in_print_def",
                args=CallArguments(args=(), kwargs={}),
                target=None,
            ),
        },
    }

    assert example_func_analyser.on_def("example", mock_call, mock_context) == {
        "gets": {Name("get_in_example_def")},
        "sets": {Name("set_in_example_def")},
        "dels": {Name("del_in_example_def")},
        "calls": {
            Call(
                name="call_in_example_def",
                args=CallArguments(args=(), kwargs={}),
                target=None,
            ),
        },
    }


def test_custom_function_analyser_on_call(
    builtin_print_analyser: CustomFunctionAnalyser,
    example_func_analyser: CustomFunctionAnalyser,
):
    mock_call = mock.Mock()
    mock_context = mock.Mock()

    assert builtin_print_analyser.on_call("print", mock_call, mock_context) == {
        "gets": {Name("get_in_print")},
        "sets": {Name("set_in_print")},
        "dels": {Name("del_in_print")},
        "calls": {
            Call(
                name="call_in_print",
                args=CallArguments(args=(), kwargs={}),
                target=None,
            ),
        },
    }

    assert example_func_analyser.on_call("example", mock_call, mock_context) == {
        "gets": {Name("get_in_example")},
        "sets": {Name("set_in_example")},
        "dels": {Name("del_in_example")},
        "calls": {
            Call(
                name="call_in_example",
                args=CallArguments(args=(), kwargs={}),
                target=None,
            ),
        },
    }
