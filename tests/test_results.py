from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from rattr.models.ir import FileIr
from rattr.models.results.file import FileResults
from rattr.models.symbol import (
    Call,
    CallArguments,
    CallInterface,
    Class,
    Func,
    Name,
)
from rattr.models.util import serialise
from rattr.results import generate_results_from_ir
from tests.shared import Import_

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests.shared import FileIrFromDictFn, MakeRootContextFn, StateFn


@pytest.fixture(autouse=True)
def __set_current_file(state: StateFn) -> Iterator[None]:
    with state(current_file=Path(__file__)):
        yield


class TestResults:
    def test_generate_results_from_ir_no_calls(
        self,
        make_root_context: MakeRootContextFn,
    ):
        # No calls
        fn = Func(name="fn", interface=CallInterface(args=("arg",)))
        fn_ir = {
            "gets": {Name("arg.another_attr", "arg")},
            "sets": {Name("arg.attr", "arg")},
            "dels": set(),
            "calls": set(),
        }
        file_ir = FileIr(
            context=make_root_context([fn], include_root_symbols=True),
            file_ir={fn: fn_ir},
        )

        expected = FileResults(
            function_results={
                "fn": {
                    "gets": {"arg.another_attr"},
                    "sets": {"arg.attr"},
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert generate_results_from_ir(target_ir=file_ir, import_irs={}) == expected

    def test_generate_results_from_ir_simple(
        self,
        make_root_context: MakeRootContextFn,
    ):
        # Calls
        fn_a = Func(name="fn_a", interface=CallInterface(args=("arg",)))
        fn_b = Func(name="fn_b", interface=CallInterface(args=("arg_b",)))
        fn_a_ir = {
            "gets": {Name("arg.another_attr", "arg")},
            "sets": {Name("arg.attr", "arg")},
            "dels": set(),
            "calls": {
                Call(name="fn_b", args=CallArguments(args=("arg",)), target=fn_b),
            },
        }
        fn_b_ir = {
            "gets": {Name("arg_b.get_in_fn_b", "arg_b")},
            "sets": {Name("arg_b.set_in_fn_b", "arg_b")},
            "dels": set(),
            "calls": set(),
        }
        file_ir = FileIr(
            context=make_root_context([fn_a, fn_b], include_root_symbols=True),
            file_ir={
                fn_a: fn_a_ir,
                fn_b: fn_b_ir,
            },
        )

        expected = FileResults(
            function_results={
                "fn_a": {
                    "gets": {"arg.another_attr", "arg.get_in_fn_b"},
                    "sets": {"arg.attr", "arg.set_in_fn_b"},
                    "dels": set(),
                    "calls": {"fn_b()"},
                },
                "fn_b": {
                    "gets": {"arg_b.get_in_fn_b"},
                    "sets": {"arg_b.set_in_fn_b"},
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert generate_results_from_ir(target_ir=file_ir, import_irs={}) == expected

    def test_generate_results_from_ir_direct_recursion(
        self,
        make_root_context: MakeRootContextFn,
    ):
        # Direct recursion
        fn = Func(name="fn", interface=CallInterface(args=("arg",)))
        fn_ir = {
            "gets": {Name("arg.another_attr", "arg")},
            "sets": {Name("arg.attr", "arg")},
            "dels": set(),
            "calls": {Call(name="fn()", args=CallArguments(args=("arg",)))},
        }
        file_ir = FileIr(
            context=make_root_context([fn], include_root_symbols=True),
            file_ir={fn: fn_ir},
        )

        expected = FileResults(
            function_results={
                "fn": {
                    "gets": {"arg.another_attr"},
                    "sets": {"arg.attr"},
                    "dels": set(),
                    "calls": {"fn()"},
                }
            },
        )

        assert generate_results_from_ir(target_ir=file_ir, import_irs={}) == expected

    def test_generate_results_from_ir_indirect_recursion(
        self,
        make_root_context: MakeRootContextFn,
    ):
        # Indirect recursion
        fn_a = Func(name="fn_a", interface=CallInterface(args=("arg_a",)))
        fn_b = Func(name="fn_b", interface=CallInterface(args=("arg_b",)))
        fn_a_ir = {
            "gets": set(),
            "sets": {Name("arg_a.get_from_a", "arg_a")},
            "dels": set(),
            "calls": {
                Call(name="fn_b", args=CallArguments(args=("arg_a",)), target=fn_b),
            },
        }
        fn_b_ir = {
            "gets": set(),
            "sets": {Name("arg_b.get_from_b", "arg_b")},
            "dels": set(),
            "calls": {
                Call(name="fn_a", args=CallArguments(args=("arg_b",)), target=fn_a),
            },
        }
        file_ir = FileIr(
            context=make_root_context([fn_a, fn_b], include_root_symbols=True),
            file_ir={
                fn_a: fn_a_ir,
                fn_b: fn_b_ir,
            },
        )

        expected = FileResults(
            function_results={
                "fn_a": {
                    "gets": set(),
                    "sets": {"arg_a.get_from_a", "arg_a.get_from_b"},
                    "dels": set(),
                    "calls": {"fn_b()"},
                },
                "fn_b": {
                    "gets": set(),
                    "sets": {"arg_b.get_from_a", "arg_b.get_from_b"},
                    "dels": set(),
                    "calls": {"fn_a()"},
                },
            },
        )

        assert generate_results_from_ir(target_ir=file_ir, import_irs={}) == expected

    def test_generate_results_from_ir_child_has_direct_recursion(
        self,
        make_root_context: MakeRootContextFn,
    ):
        fn_a = Func(name="fn_a", interface=CallInterface(args=("x",)))
        fn_b = Func(name="fn_b", interface=CallInterface(args=("arg",)))
        fn_a_ir = {
            "gets": {Name("x.attr", "x")},
            "sets": set(),
            "dels": set(),
            "calls": {
                Call(name="fn_b", args=CallArguments(args=("x",)), target=fn_b),
            },
        }
        fn_b_ir = {
            "gets": {Name("arg.field", "arg")},
            "sets": set(),
            "dels": set(),
            "calls": {
                Call(name="fn_b", args=CallArguments(args=("arg",)), target=fn_b),
            },
        }
        file_ir = FileIr(
            context=make_root_context([fn_a, fn_b], include_root_symbols=True),
            file_ir={
                fn_a: fn_a_ir,
                fn_b: fn_b_ir,
            },
        )

        expected = FileResults(
            function_results={
                "fn_a": {
                    "gets": {"x.attr", "x.field"},
                    "sets": set(),
                    "dels": set(),
                    "calls": {"fn_b()"},
                },
                "fn_b": {
                    "gets": {"arg.field"},
                    "sets": set(),
                    "dels": set(),
                    "calls": {"fn_b()"},
                },
            },
        )

        assert generate_results_from_ir(target_ir=file_ir, import_irs={}) == expected

    def test_generate_results_from_ir_child_has_indirect_recursion(
        self,
        make_root_context: MakeRootContextFn,
    ):
        fn_a = Func(name="fn_a", interface=CallInterface(args=("a",)))
        fn_b = Func(name="fn_b", interface=CallInterface(args=("b",)))
        fn_c = Func(name="fn_c", interface=CallInterface(args=("c",)))
        fn_a_ir = {
            "gets": {Name("a.in_a", "a")},
            "sets": set(),
            "dels": set(),
            "calls": {
                Call(
                    name="fn_b",
                    args=CallArguments(args=("a",), kwargs={}),
                    target=fn_b,
                ),
            },
        }
        fn_b_ir = {
            "gets": {Name("b.in_b", "b")},
            "sets": set(),
            "dels": set(),
            "calls": {
                Call(
                    name="fn_c",
                    args=CallArguments(args=("b",), kwargs={}),
                    target=fn_c,
                ),
            },
        }
        fn_c_ir = {
            "gets": {Name("c.in_c", "c")},
            "sets": set(),
            "dels": set(),
            "calls": {
                Call(
                    name="fn_b",
                    args=CallArguments(args=(), kwargs={"b": "c"}),
                    target=fn_b,
                ),
            },
        }
        file_ir = FileIr(
            context=make_root_context([fn_a, fn_b, fn_c], include_root_symbols=True),
            file_ir={
                fn_a: fn_a_ir,
                fn_b: fn_b_ir,
                fn_c: fn_c_ir,
            },
        )

        expected = FileResults(
            function_results={
                "fn_a": {
                    "gets": {"a.in_a", "a.in_b", "a.in_c"},
                    "sets": set(),
                    "dels": set(),
                    "calls": {"fn_b()"},
                },
                "fn_b": {
                    "gets": {"b.in_b", "b.in_c"},
                    "sets": set(),
                    "dels": set(),
                    "calls": {"fn_c()"},
                },
                "fn_c": {
                    "gets": {"c.in_b", "c.in_c"},
                    "sets": set(),
                    "dels": set(),
                    "calls": {"fn_b()"},
                },
            },
        )

        assert generate_results_from_ir(target_ir=file_ir, import_irs={}) == expected

    def test_generate_results_from_ir_repeated_calls_should_be_ignored(
        self,
        make_root_context: MakeRootContextFn,
    ):
        fn_a = Func(name="fn_a", interface=CallInterface(args=("a",)))
        fn_b = Func(name="fn_b", interface=CallInterface(args=("b",)))
        fn_a_ir = {
            "gets": {Name("a.in_a", "a")},
            "sets": set(),
            "dels": set(),
            "calls": {
                Call(name="fn_b", args=CallArguments(args=("a.attr",)), target=fn_b),
                Call(name="fn_b", args=CallArguments(args=("a.attr",)), target=fn_b),
            },
        }
        fn_b_ir = {
            "gets": {Name("b.in_b", "b")},
            "sets": set(),
            "dels": set(),
            "calls": set(),
        }
        file_ir = FileIr(
            context=make_root_context([fn_a, fn_b], include_root_symbols=True),
            file_ir={
                fn_a: fn_a_ir,
                fn_b: fn_b_ir,
            },
        )

        expected = FileResults(
            function_results={
                "fn_a": {
                    "gets": {"a.in_a", "a.attr.in_b"},
                    "sets": set(),
                    "dels": set(),
                    "calls": {"fn_b()"},
                },
                "fn_b": {
                    "gets": {"b.in_b"},
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert generate_results_from_ir(target_ir=file_ir, import_irs={}) == expected

    def test_generate_results_from_ir_repeated_calls_should_not_be_ignored(
        self,
        make_root_context: MakeRootContextFn,
    ):
        # Should not be ignored as they have different call signatures
        fn_a = Func(name="fn_a", interface=CallInterface(args=("a",)))
        fn_b = Func(name="fn_b", interface=CallInterface(args=("b",)))
        fn_a_ir = {
            "gets": {Name("a.in_a", "a")},
            "sets": set(),
            "dels": set(),
            "calls": {
                Call(
                    name="fn_b",
                    args=CallArguments(args=("a.attr_one",)),
                    target=fn_b,
                ),
                Call(
                    name="fn_b",
                    args=CallArguments(args=("a.attr_two",)),
                    target=fn_b,
                ),
            },
        }
        fn_b_ir = {
            "gets": {Name("b.in_b", "b")},
            "sets": set(),
            "dels": set(),
            "calls": set(),
        }
        file_ir = FileIr(
            context=make_root_context([fn_a, fn_b], include_root_symbols=True),
            file_ir={
                fn_a: fn_a_ir,
                fn_b: fn_b_ir,
            },
        )

        expected = FileResults(
            function_results={
                "fn_a": {
                    "gets": {"a.in_a", "a.attr_one.in_b", "a.attr_two.in_b"},
                    "sets": set(),
                    "dels": set(),
                    "calls": {"fn_b()"},
                },
                "fn_b": {
                    "gets": {"b.in_b"},
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert generate_results_from_ir(target_ir=file_ir, import_irs={}) == expected

    def test_import_irs(
        self,
        file_ir_from_dict: FileIrFromDictFn,
        make_root_context: MakeRootContextFn,
    ):
        act = Func(name="act", interface=CallInterface(args=("arg",)))
        import_irs = {
            "module": file_ir_from_dict(
                {
                    act: {
                        "gets": {Name("arg.attr", "arg")},
                        "sets": set(),
                        "dels": set(),
                        "calls": set(),
                    }
                }
            )
        }

        import_ = Import_(
            name="act",
            qualified_name="module.act",
            module_name_and_spec=("module", mock.Mock()),
        )

        fn = Func(name="fn", interface=CallInterface(args=("ms",)))
        fn_ir = {
            "gets": set(),
            "sets": set(),
            "dels": set(),
            "calls": {
                Call(name="act", args=CallArguments(args=("ms",)), target=import_)
            },
        }
        file_ir = FileIr(
            context=make_root_context([import_, fn], include_root_symbols=True),
            file_ir={fn: fn_ir},
        )

        expected = FileResults(
            function_results={
                "fn": {
                    "gets": {"ms.attr"},
                    "sets": set(),
                    "dels": set(),
                    "calls": {"act()"},
                }
            },
        )

        assert (
            generate_results_from_ir(target_ir=file_ir, import_irs=import_irs)
            == expected
        )

    def test_import_irs_chained_import(
        self,
        file_ir_from_dict: FileIrFromDictFn,
        make_root_context: MakeRootContextFn,
    ):
        import_second = Import_(
            name="second",
            qualified_name="chained.second",
            module_name_and_spec=("chained", mock.Mock()),
        )

        first = Func(name="first", interface=CallInterface(args=("arrg",)))
        second = Func(name="second", interface=CallInterface(args=("blarg",)))
        import_irs = {
            "module": file_ir_from_dict(
                {
                    first: {
                        "gets": set(),
                        "sets": set(),
                        "dels": set(),
                        "calls": {
                            Call(
                                name="second",
                                args=CallArguments(args=("arrg",)),
                                target=import_second,
                            ),
                        },
                    }
                }
            ),
            "chained": file_ir_from_dict(
                {
                    second: {
                        "gets": {Name("blarg._attr", "blarg")},
                        "sets": set(),
                        "dels": set(),
                        "calls": set(),
                    }
                }
            ),
        }

        import_first = Import_(
            name="first",
            qualified_name="module.first",
            module_name_and_spec=("module", mock.Mock()),
        )

        fn = Func(name="fn", interface=CallInterface(args=("flarg",)))
        fn_ir = {
            "gets": set(),
            "sets": set(),
            "dels": set(),
            "calls": {
                Call(
                    name="first",
                    args=CallArguments(args=("flarg",)),
                    target=import_first,
                ),
            },
        }
        file_ir = FileIr(
            context=make_root_context([fn, import_first], include_root_symbols=True),
            file_ir={fn: fn_ir},
        )

        expected = FileResults(
            function_results={
                "fn": {
                    "gets": {"flarg._attr"},
                    "sets": set(),
                    "dels": set(),
                    "calls": {"first()"},
                }
            },
        )

        assert (
            generate_results_from_ir(target_ir=file_ir, import_irs=import_irs)
            == expected
        )

    def test_class(self, make_root_context: MakeRootContextFn):
        cls_inst = Class("SomeClass", interface=CallInterface(args=("self", "arg")))
        cls_inst_ir = {
            "gets": {Name("arg.attr_in_init", "arg")},
            "sets": {Name("self.my_attr", "self")},
            "dels": set(),
            "calls": set(),
        }
        cls_inst_sm = Func(
            name="SomeClass.static",
            interface=CallInterface(args=("flarg",)),
        )
        cls_inst_sm_ir = {
            "gets": set(),
            "sets": {Name("flarg.attr_in_static", "flarg")},
            "dels": set(),
            "calls": set(),
        }
        fn = Func(
            name="i_call_them",
            interface=CallInterface(args=("marg",)),
        )
        fn_ir = {
            "gets": set(),
            "sets": {Name("instance")},
            "dels": set(),
            "calls": {
                Call(
                    name="SomeClass()",
                    args=CallArguments(args=("instance", "marg")),
                    target=cls_inst,
                ),
                Call(
                    name="SomeClass.static()",
                    args=CallArguments(args=("marg",)),
                    target=cls_inst_sm,
                ),
            },
        }
        file_ir = FileIr(
            context=make_root_context(
                [
                    cls_inst,
                    cls_inst_sm,
                    fn,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                cls_inst: cls_inst_ir,
                cls_inst_sm: cls_inst_sm_ir,
                fn: fn_ir,
            },
        )

        expected = FileResults(
            function_results={
                "SomeClass": {
                    "gets": {"arg.attr_in_init"},
                    "sets": {"self.my_attr"},
                    "dels": set(),
                    "calls": set(),
                },
                "SomeClass.static": {
                    "gets": set(),
                    "sets": {"flarg.attr_in_static"},
                    "dels": set(),
                    "calls": set(),
                },
                "i_call_them": {
                    "gets": {
                        "marg.attr_in_init",
                    },
                    "sets": {
                        "instance",
                        "instance.my_attr",
                        "marg.attr_in_static",
                    },
                    "dels": set(),
                    "calls": {
                        "SomeClass()",
                        "SomeClass.static()",
                    },
                },
            },
        )

        assert generate_results_from_ir(target_ir=file_ir, import_irs={}) == expected


class TestResultsEncoder:
    @pytest.fixture
    def example_file_results_unordered(self):
        return {
            "my_func": {
                "gets": {
                    "z_should_come_after_a",
                    "z_should_come_after_a.yet_it_did_not",
                    "a_should_come_before_z",
                    "a_should_come_before_z[]",
                    "argument.attrs[].whatever.item",
                    "@ListComp",
                    "@Str",
                },
                "sets": {
                    "z_should_come_after_a",
                    "a_should_come_before_z",
                },
                "dels": {
                    "a_should_come_before_z",
                    "z_should_come_after_a",
                },
                "calls": {
                    "my_amazing_function()",
                    "your_amazing_function()",
                    "library.your_amazing_function()",
                    "argument.callbacks[].exec()",
                },
            }
        }

    @pytest.fixture
    def example_file_results_ordered_str(self):
        return dedent(
            """\
            {
                "my_func": {
                    "gets": [
                        "@ListComp",
                        "@Str",
                        "a_should_come_before_z",
                        "a_should_come_before_z[]",
                        "argument.attrs[].whatever.item",
                        "z_should_come_after_a",
                        "z_should_come_after_a.yet_it_did_not"
                    ],
                    "sets": [
                        "a_should_come_before_z",
                        "z_should_come_after_a"
                    ],
                    "dels": [
                        "a_should_come_before_z",
                        "z_should_come_after_a"
                    ],
                    "calls": [
                        "argument.callbacks[].exec()",
                        "library.your_amazing_function()",
                        "my_amazing_function()",
                        "your_amazing_function()"
                    ]
                }
            }"""
        )

    def test_is_sorted_from_unordered_container(
        self,
        example_file_results_unordered,
        example_file_results_ordered_str,
    ):
        assert (
            serialise(FileResults(example_file_results_unordered), indent=4)
            == example_file_results_ordered_str
        )
