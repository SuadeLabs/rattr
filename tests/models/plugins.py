from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from rattr.models.plugins import Plugins
from rattr.models.symbol import Builtin, CallInterface, Func, Import

if TYPE_CHECKING:
    from rattr.analyser.base import Assertor, CustomFunctionAnalyser


@pytest.fixture
def example_plugins(
    example_assertor: Assertor,
    builtin_print_analyser: CustomFunctionAnalyser,
    example_func_analyser: CustomFunctionAnalyser,
):
    return Plugins(
        assertors=[example_assertor],
        analysers=[builtin_print_analyser, example_func_analyser],
    )


def test_register_assertors(example_assertor: Assertor):
    plugins = Plugins()
    assert plugins.assertors == []

    plugins.register_assertors((example_assertor, example_assertor, example_assertor))
    assert plugins.assertors == [example_assertor]


def test_register_analysers(
    builtin_print_analyser: CustomFunctionAnalyser,
    example_func_analyser: CustomFunctionAnalyser,
):
    plugins = Plugins()
    assert plugins.analysers == []

    plugins.register_analysers(
        (
            builtin_print_analyser,
            example_func_analyser,
            example_func_analyser,
        )
    )
    assert plugins.analysers == [example_func_analyser]


def test_plugins_has_analyser(example_plugins: Plugins):
    assert example_plugins.has_analyser(Builtin("print"))
    assert not example_plugins.has_analyser(Builtin("getattr"))


@pytest.mark.parametrize("modulename", [None, "module", "bleep.bloop"])
def test_plugins_get_analyser_builtin(
    example_plugins: Plugins,
    builtin_print_analyser: CustomFunctionAnalyser,
    modulename: str | None,
):
    assert (
        example_plugins.get_analyser(Builtin("print"), modulename=modulename)
        == builtin_print_analyser
    )
    assert (
        example_plugins.get_analyser(Builtin("not_print"), modulename=modulename)
        is None
    )


def test_plugins_get_analyser_local_function_positive(
    example_plugins: Plugins,
    example_func_analyser: CustomFunctionAnalyser,
):
    assert (
        example_plugins.get_analyser(
            Func("example", interface=CallInterface()),
            modulename=None,
        )
        == example_func_analyser
    )
    assert (
        example_plugins.get_analyser(
            Func("example", interface=CallInterface()),
            modulename="module",
        )
        == example_func_analyser
    )
    assert (
        example_plugins.get_analyser(
            Func("example", interface=CallInterface()),
            modulename="not_the_module_example.is_defined_in",
        )
        is None
    )


@pytest.mark.parametrize("modulename", [None, "module", "bleep.bloop"])
def test_plugins_get_analyser_local_function_negative(
    example_plugins: Plugins,
    modulename: str | None,
):
    assert (
        example_plugins.get_analyser(
            Func("nope", interface=CallInterface()),
            modulename=modulename,
        )
        is None
    )


@pytest.mark.parametrize("modulename", [None, "module", "bleep.bloop"])
def test_plugins_get_analyser_import_positive(
    example_plugins: Plugins,
    example_func_analyser: CustomFunctionAnalyser,
    modulename: str | None,
):
    assert (
        example_plugins.get_analyser(
            Import(name="example", qualified_name="different.module.example"),
            modulename=modulename,
        )
        is None
    )
    assert (
        example_plugins.get_analyser(
            Import(name="example", qualified_name="module.example"),
            modulename=modulename,
        )
        == example_func_analyser
    )


@pytest.mark.parametrize("modulename", [None, "module", "bleep.bloop"])
def test_plugins_get_analyser_import_negative(
    example_plugins: Plugins,
    modulename: str | None,
):
    assert (
        example_plugins.get_analyser(
            Import(name="no_analyser", qualified_name="different.module.no_analyser"),
            modulename=modulename,
        )
        is None
    )
    assert (
        example_plugins.get_analyser(
            Import(name="no_analyser", qualified_name="module.no_analyser"),
            modulename=modulename,
        )
        is None
    )
