from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from rattr.models.ir import FileIr
from rattr.models.symbol import (
    Builtin,
    Call,
    CallArguments,
    CallInterface,
    Class,
    Func,
    Import,
)
from rattr.results._find_call_target import find_call_target_and_ir
from rattr.results._types import IrCall, IrEnvironment, IrTarget
from tests.shared import Import_, match_output

if TYPE_CHECKING:
    from typing import Literal

    from tests.shared import FileIrFromDictFn


@pytest.fixture()
def dummy_caller() -> mock.Mock:
    return mock.Mock()


def test_find_call_target_and_ir_target_is_not_defined_in_env(
    dummy_caller: mock.Mock,
    example_environment_a: IrEnvironment,
):
    call = IrCall(
        caller=dummy_caller,
        symbol=Call(name="some_func()", args=CallArguments(), target=None),
    )
    assert find_call_target_and_ir(call, environment=example_environment_a) is None


def test_find_call_target_and_ir_target_is_a_builtin(
    dummy_caller: mock.Mock,
    example_environment_a: IrEnvironment,
):
    call = IrCall(
        caller=dummy_caller,
        symbol=Call(name="max()", args=CallArguments(), target=Builtin("max")),
    )
    assert find_call_target_and_ir(call, environment=example_environment_a) is None


@pytest.mark.parametrize("fn", ["a", "b"])
def test_find_call_target_and_ir_target_is_func_defined_in_env(
    dummy_caller: mock.Mock,
    example_environment_a: IrEnvironment,
    example_file_ir_a: FileIr,
    fn: Literal["a", "b"],
):
    fn_symbol = Func(name=f"fn_{fn}", interface=CallInterface())
    fn_call = IrCall(
        caller=dummy_caller,
        symbol=Call(name=f"fn_{fn}()", args=CallArguments(), target=fn_symbol),
    )
    fn_ir = example_file_ir_a[fn_symbol]

    actual = find_call_target_and_ir(fn_call, environment=example_environment_a)
    expected = IrTarget(symbol=fn_symbol, ir=fn_ir)

    assert actual == expected


def test_find_call_target_and_ir_target_is_a_class_init_defined_in_env(
    dummy_caller: mock.Mock,
    example_environment_a: IrEnvironment,
    example_file_ir_a: FileIr,
):
    cls_symbol = Class(name="ClassA", interface=CallInterface(args=("self", "arg")))
    cls_call = IrCall(
        caller=dummy_caller,
        symbol=Call(
            name="ClassA()",
            args=CallArguments(args=("a",)),
            target=cls_symbol,
        ),
    )
    cls_ir = example_file_ir_a[cls_symbol]

    actual = find_call_target_and_ir(cls_call, environment=example_environment_a)
    expected = IrTarget(symbol=cls_symbol, ir=cls_ir)

    assert actual == expected


@pytest.mark.pypy()
def test_find_call_target_and_ir_target_is_in_stdlib(
    example_environment_a: IrEnvironment,
):
    stdlib_call_symbol = Call(
        name="sin()",
        args=CallArguments(),
        target=Import("sin", "math.sin"),
    )
    assert stdlib_call_symbol.target.module_name == "math"

    actual = find_call_target_and_ir(
        IrCall(
            mock.Mock(),  # unused when symbol is an import
            symbol=stdlib_call_symbol,
        ),
        environment=example_environment_a,
    )
    assert actual is None


def test_find_call_target_and_ir_target_is_imported(
    dummy_caller: mock.Mock,
    example_file_ir_a: FileIr,
    file_ir_from_dict: FileIrFromDictFn,
):
    fn = Func(name="fn", interface=CallInterface())
    fn_ir = {
        "sets": set(),
        "gets": set(),
        "dels": set(),
        "calls": set(),
    }
    expected = IrTarget(symbol=fn, ir=fn_ir)

    environment = IrEnvironment(
        target_ir=example_file_ir_a,
        import_irs={"module": file_ir_from_dict({fn: fn_ir})},
    )

    call = IrCall(
        caller=dummy_caller,
        symbol=Call(
            name="fn()",
            args=CallArguments(),
            target=Import_(
                "fn",
                "module.fn",
                module_name_and_spec=("module", mock.Mock()),
            ),
        ),
    )

    assert find_call_target_and_ir(call, environment=environment) == expected


def test_find_call_target_and_ir_target_is_import_undefined_in_module(
    dummy_caller: mock.Mock,
    example_file_ir_a: FileIr,
    file_ir_from_dict: FileIrFromDictFn,
    capfd: pytest.CaptureFixture[str],
):
    fn = Func(name="fn", interface=CallInterface())
    fn_ir = {
        "sets": set(),
        "gets": set(),
        "dels": set(),
        "calls": set(),
    }

    environment = IrEnvironment(
        target_ir=example_file_ir_a,
        import_irs={"module": file_ir_from_dict({fn: fn_ir})},
    )

    call = IrCall(
        caller=dummy_caller,
        symbol=Call(
            name="nope()",
            args=CallArguments(),
            target=Import_(
                "nope",
                "module.nope",
                module_name_and_spec=("module", mock.Mock()),
            ),
        ),
    )
    assert find_call_target_and_ir(call, environment=environment) is None

    _, stderr = capfd.readouterr()
    assert match_output(
        stderr,
        [
            "unable to resolve call to 'nope' in import 'module', "
            "it is likely undefined",
        ],
    )


def test_find_call_target_and_ir_target_is_import_in_undefined_module(
    dummy_caller: mock.Mock,
    example_file_ir_a: FileIr,
    file_ir_from_dict: FileIrFromDictFn,
):
    fn = Func(name="fn", interface=CallInterface())
    fn_ir = {
        "sets": set(),
        "gets": set(),
        "dels": set(),
        "calls": set(),
    }

    environment = IrEnvironment(
        target_ir=example_file_ir_a,
        import_irs={"module": file_ir_from_dict({fn: fn_ir})},
    )

    call = IrCall(
        caller=dummy_caller,
        symbol=Call(
            name="nah()",
            args=CallArguments(),
            target=Import_(
                "nah",
                "noway.nah",
                module_name_and_spec=("noway", mock.Mock()),
            ),
        ),
    )
    with pytest.raises(ImportError):
        assert find_call_target_and_ir(call, environment=environment) is None
