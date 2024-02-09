from __future__ import annotations

import json
from textwrap import dedent
from unittest import mock

import pytest

from rattr.analyser.results import ResultsEncoder, generate_results_from_ir
from rattr.models.symbol import (
    Call,
    CallArguments,
    CallInterface,
    Class,
    Func,
    Import,
    Name,
)


class TestResults:
    def test_generate_results_from_ir_no_calls(self):
        # No calls
        fn = Func(name="fn", interface=CallInterface(args=("arg",)))
        fn_ir = {
            "sets": {
                Name("arg.attr", "arg"),
            },
            "gets": {
                Name("arg.another_attr", "arg"),
            },
            "dels": set(),
            "calls": set(),
        }
        file_ir = {fn: fn_ir}

        expected = {
            "fn": {
                "sets": {"arg.attr"},
                "gets": {"arg.another_attr"},
                "dels": set(),
                "calls": set(),
            }
        }

        assert generate_results_from_ir(file_ir, dict()) == expected

    def test_generate_results_from_ir_simple(self):
        # Calls
        fn_a = Func(name="fn_a", interface=CallInterface(args=("arg",)))
        fn_b = Func(name="fn_b", interface=CallInterface(args=("arg_b",)))
        fn_a_ir = {
            "sets": {
                Name("arg.attr", "arg"),
            },
            "gets": {
                Name("arg.another_attr", "arg"),
            },
            "dels": set(),
            "calls": {
                Call(name="fn_b", args=CallArguments(args=("arg",)), target=fn_b),
            },
        }
        fn_b_ir = {
            "sets": {
                Name("arg_b.set_in_fn_b", "arg_b"),
            },
            "gets": {
                Name("arg_b.get_in_fn_b", "arg_b"),
            },
            "dels": set(),
            "calls": set(),
        }
        file_ir = {
            fn_a: fn_a_ir,
            fn_b: fn_b_ir,
        }

        expected = {
            "fn_a": {
                "sets": {"arg.attr", "arg.set_in_fn_b"},
                "gets": {"arg.another_attr", "arg.get_in_fn_b"},
                "dels": set(),
                "calls": {"fn_b()"},
            },
            "fn_b": {
                "sets": {"arg_b.set_in_fn_b"},
                "gets": {"arg_b.get_in_fn_b"},
                "dels": set(),
                "calls": set(),
            },
        }

        assert generate_results_from_ir(file_ir, dict()) == expected

    def test_generate_results_from_ir_direct_recursion(self):
        # Direct recursion
        fn = Func(name="fn", interface=CallInterface(args=("arg",)))
        fn_ir = {
            "sets": {
                Name("arg.attr", "arg"),
            },
            "gets": {
                Name("arg.another_attr", "arg"),
            },
            "dels": set(),
            "calls": {Call(name="fn()", args=CallArguments(args=("arg",)))},
        }
        file_ir = {fn: fn_ir}

        expected = {
            "fn": {
                "sets": {"arg.attr"},
                "gets": {"arg.another_attr"},
                "dels": set(),
                "calls": {"fn()"},
            }
        }

        assert generate_results_from_ir(file_ir, dict()) == expected

    def test_generate_results_from_ir_indirect_recursion(self):
        # Indirect recursion
        fn_a = Func(name="fn_a", interface=CallInterface(args=("arg_a",)))
        fn_b = Func(name="fn_b", interface=CallInterface(args=("arg_b",)))
        fn_a_ir = {
            "sets": {Name("arg_a.get_from_a", "arg_a")},
            "gets": set(),
            "dels": set(),
            "calls": {
                Call(name="fn_b", args=CallArguments(args=("arg_a",)), target=fn_b),
            },
        }
        fn_b_ir = {
            "sets": {Name("arg_b.get_from_b", "arg_b")},
            "gets": set(),
            "dels": set(),
            "calls": {
                Call(name="fn_a", args=CallArguments(args=("arg_b",)), target=fn_a),
            },
        }
        file_ir = {
            fn_a: fn_a_ir,
            fn_b: fn_b_ir,
        }

        expected = {
            "fn_a": {
                "sets": {"arg_a.get_from_a", "arg_a.get_from_b"},
                "gets": set(),
                "dels": set(),
                "calls": {"fn_b()"},
            },
            "fn_b": {
                "sets": {"arg_b.get_from_a", "arg_b.get_from_b"},
                "gets": set(),
                "dels": set(),
                "calls": {"fn_a()"},
            },
        }

        assert generate_results_from_ir(file_ir, dict()) == expected

    def test_generate_results_from_ir_child_has_direct_recursion(self):
        fn_a = Func(name="fn_a", interface=CallInterface(args=("x",)))
        fn_b = Func(name="fn_b", interface=CallInterface(args=("arg",)))
        fn_a_ir = {
            "sets": set(),
            "gets": {Name("x.attr", "x")},
            "dels": set(),
            "calls": {
                Call(name="fn_b", args=CallArguments(args=("x",)), target=fn_b),
            },
        }
        fn_b_ir = {
            "sets": set(),
            "gets": {Name("arg.field", "arg")},
            "dels": set(),
            "calls": {
                Call(name="fn_b", args=CallArguments(args=("arg",)), target=fn_b),
            },
        }
        file_ir = {
            fn_a: fn_a_ir,
            fn_b: fn_b_ir,
        }

        expected = {
            "fn_a": {
                "sets": set(),
                "gets": {"x.attr", "x.field"},
                "dels": set(),
                "calls": {"fn_b()"},
            },
            "fn_b": {
                "sets": set(),
                "gets": {"arg.field"},
                "dels": set(),
                "calls": {"fn_b()"},
            },
        }

        assert generate_results_from_ir(file_ir, dict()) == expected

    def test_generate_results_from_ir_child_has_indirect_recursion(self):
        fn_a = Func(name="fn_a", interface=CallInterface(args=("a",)))
        fn_b = Func(name="fn_b", interface=CallInterface(args=("b",)))
        fn_c = Func(name="fn_c", interface=CallInterface(args=("c",)))
        fn_a_ir = {
            "sets": set(),
            "gets": {Name("a.in_a", "a")},
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
            "sets": set(),
            "gets": {Name("b.in_b", "b")},
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
            "sets": set(),
            "gets": {Name("c.in_c", "c")},
            "dels": set(),
            "calls": {
                Call(
                    name="fn_b",
                    args=CallArguments(args=(), kwargs={"b": "c"}),
                    target=fn_b,
                ),
            },
        }
        file_ir = {
            fn_a: fn_a_ir,
            fn_b: fn_b_ir,
            fn_c: fn_c_ir,
        }

        expected = {
            "fn_a": {
                "sets": set(),
                "gets": {"a.in_a", "a.in_b", "a.in_c"},
                "dels": set(),
                "calls": {"fn_b()"},
            },
            "fn_b": {
                "sets": set(),
                "gets": {"b.in_b", "b.in_c"},
                "dels": set(),
                "calls": {"fn_c()"},
            },
            "fn_c": {
                "sets": set(),
                "gets": {"c.in_b", "c.in_c"},
                "dels": set(),
                "calls": {"fn_b()"},
            },
        }

        assert generate_results_from_ir(file_ir, dict()) == expected

    def test_generate_results_from_ir_repeated_calls(self):
        # Repeated calls that should be ignored
        fn_a = Func(name="fn_a", interface=CallInterface(args=("a",)))
        fn_b = Func(name="fn_b", interface=CallInterface(args=("b",)))
        fn_a_ir = {
            "sets": set(),
            "gets": {Name("a.in_a", "a")},
            "dels": set(),
            "calls": {
                Call(name="fn_b", args=CallArguments(args=("a.attr",)), target=fn_b),
                Call(name="fn_b", args=CallArguments(args=("a.attr",)), target=fn_b),
            },
        }
        fn_b_ir = {
            "sets": set(),
            "gets": {Name("b.in_b", "b")},
            "dels": set(),
            "calls": set(),
        }
        file_ir = {
            fn_a: fn_a_ir,
            fn_b: fn_b_ir,
        }

        expected = {
            "fn_a": {
                "sets": set(),
                "gets": {"a.in_a", "a.attr.in_b"},
                "dels": set(),
                "calls": {"fn_b()"},
            },
            "fn_b": {
                "sets": set(),
                "gets": {"b.in_b"},
                "dels": set(),
                "calls": set(),
            },
        }

        assert generate_results_from_ir(file_ir, dict()) == expected

        # Repeated calls that should not be ignored
        fn_a_ir = {
            "sets": set(),
            "gets": {Name("a.in_a", "a")},
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
            "sets": set(),
            "gets": {Name("b.in_b", "b")},
            "dels": set(),
            "calls": set(),
        }
        file_ir = {
            fn_a: fn_a_ir,
            fn_b: fn_b_ir,
        }

        expected = {
            "fn_a": {
                "sets": set(),
                "gets": {"a.in_a", "a.attr_one.in_b", "a.attr_two.in_b"},
                "dels": set(),
                "calls": {"fn_b()"},
            },
            "fn_b": {
                "sets": set(),
                "gets": {"b.in_b"},
                "dels": set(),
                "calls": set(),
            },
        }

        assert generate_results_from_ir(file_ir, dict()) == expected

    def test_imports_ir(self, file_ir_from_dict):
        # Simple
        act = Func(name="act", interface=CallInterface(args=("arg",)))
        imports_ir = {
            "module": file_ir_from_dict(
                {
                    act: {
                        "sets": set(),
                        "gets": {
                            Name("arg.attr", "arg"),
                        },
                        "dels": set(),
                        "calls": set(),
                    }
                }
            )
        }

        _i = Import(name="act", qualified_name="module.act")
        _i.module_name = "module"
        _i.module_spec = mock.Mock()

        fn = Func(name="fn", interface=CallInterface(args=("ms",)))
        fn_ir = {
            "sets": set(),
            "gets": set(),
            "dels": set(),
            "calls": {Call(name="act", args=CallArguments(args=("ms",)), target=_i)},
        }
        file_ir = {
            fn: fn_ir,
        }

        expected = {
            "fn": {
                "sets": set(),
                "gets": {"ms.attr"},
                "dels": set(),
                "calls": {"act()"},
            }
        }

        assert generate_results_from_ir(file_ir, imports_ir) == expected

        # Chained
        _i_second = Import(name="second", qualified_name="chained.second")
        _i_second.module_name = "chained"
        _i_second.module_spec = mock.Mock()

        first = Func(name="first", interface=CallInterface(args=("arrg",)))
        second = Func(name="second", interface=CallInterface(args=("blarg",)))
        imports_ir = {
            "module": file_ir_from_dict(
                {
                    first: {
                        "sets": set(),
                        "gets": set(),
                        "dels": set(),
                        "calls": {
                            Call(
                                name="second",
                                args=CallArguments(args=("arrg",)),
                                target=_i_second,
                            ),
                        },
                    }
                }
            ),
            "chained": file_ir_from_dict(
                {
                    second: {
                        "sets": set(),
                        "gets": {
                            Name("blarg._attr", "blarg"),
                        },
                        "dels": set(),
                        "calls": set(),
                    }
                }
            ),
        }

        _i_module = Import(name="first", qualified_name="module.first")
        _i_module.module_name = "module"
        _i_module.module_spec = mock.Mock()

        fn = Func(name="fn", interface=CallInterface(args=("flarg",)))
        fn_ir = {
            "sets": set(),
            "gets": set(),
            "dels": set(),
            "calls": {
                Call(
                    name="first",
                    args=CallArguments(args=("flarg",)),
                    target=_i_module,
                ),
            },
        }
        file_ir = {
            fn: fn_ir,
        }

        expected = {
            "fn": {
                "sets": set(),
                "gets": {"flarg._attr"},
                "dels": set(),
                "calls": {
                    "first()",
                },
            }
        }

        assert generate_results_from_ir(file_ir, imports_ir) == expected

    def test_class(self):
        cls_inst = Class("SomeClass", ["self", "arg"], None, None)
        cls_inst_ir = {
            "sets": {
                Name("self.my_attr", "self"),
            },
            "gets": {
                Name("arg.attr_in_init", "arg"),
            },
            "dels": set(),
            "calls": set(),
        }
        cls_inst_sm = Func(
            name="SomeClass.static",
            interface=CallInterface(args=("flarg",)),
        )
        cls_inst_sm_ir = {
            "sets": {
                Name("flarg.attr_in_static", "flarg"),
            },
            "gets": set(),
            "dels": set(),
            "calls": set(),
        }
        fn = Func(
            name="i_call_them",
            interface=CallInterface(args=("marg",)),
        )
        fn_ir = {
            "sets": {
                Name("instance"),
            },
            "gets": set(),
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
        file_ir = {
            cls_inst: cls_inst_ir,
            cls_inst_sm: cls_inst_sm_ir,
            fn: fn_ir,
        }

        expected = {
            "SomeClass": {
                "sets": {"self.my_attr"},
                "gets": {"arg.attr_in_init"},
                "dels": set(),
                "calls": set(),
            },
            "SomeClass.static": {
                "sets": {"flarg.attr_in_static"},
                "gets": set(),
                "dels": set(),
                "calls": set(),
            },
            "i_call_them": {
                "sets": {
                    "instance",
                    "instance.my_attr",
                    "marg.attr_in_static",
                },
                "gets": {
                    "marg.attr_in_init",
                },
                "dels": set(),
                "calls": {
                    "SomeClass()",
                    "SomeClass.static()",
                },
            },
        }

        assert generate_results_from_ir(file_ir, dict()) == expected


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
            json.dumps(example_file_results_unordered, indent=4, cls=ResultsEncoder)
            == example_file_results_ordered_str
        )
