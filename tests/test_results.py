from unittest import mock

from rattr.analyser.context import Call, Func, Import, Name
from rattr.analyser.context.symbol import Class
from rattr.analyser.results import generate_results_from_ir


class TestResults:
    def test_generate_results_from_ir_no_calls(self):
        # No calls
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
        file_ir = {Func("fn", ["arg"], None, None): fn_ir}

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
        fn_a = Func("fn_a", ["arg"], None, None)
        fn_b = Func("fn_b", ["arg_b"], None, None)
        fn_a_ir = {
            "sets": {
                Name("arg.attr", "arg"),
            },
            "gets": {
                Name("arg.another_attr", "arg"),
            },
            "dels": set(),
            "calls": {
                Call("fn_b()", ["arg"], {}, target=fn_b),
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
        fn_ir = {
            "sets": {
                Name("arg.attr", "arg"),
            },
            "gets": {
                Name("arg.another_attr", "arg"),
            },
            "dels": set(),
            "calls": {Call("fn()", ["arg"], {})},
        }
        file_ir = {Func("fn", ["arg"], None, None): fn_ir}

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
        fn_a = Func("fn_a", ["arg_a"], None, None)
        fn_b = Func("fn_b", ["arg_b"], None, None)
        fn_a_ir = {
            "sets": {Name("arg_a.get_from_a", "arg_a")},
            "gets": set(),
            "dels": set(),
            "calls": {Call("fn_b()", ["arg_a"], {}, target=fn_b)},
        }
        fn_b_ir = {
            "sets": {Name("arg_b.get_from_b", "arg_b")},
            "gets": set(),
            "dels": set(),
            "calls": {Call("fn_a()", ["arg_b"], {}, target=fn_a)},
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
        fn_a = Func("fn_a", ["x"], None, None)
        fn_b = Func("fn_b", ["arg"], None, None)
        fn_a_ir = {
            "sets": set(),
            "gets": {Name("x.attr", "x")},
            "dels": set(),
            "calls": {Call("fn_b()", ["x"], {}, target=fn_b)},
        }
        fn_b_ir = {
            "sets": set(),
            "gets": {Name("arg.field", "arg")},
            "dels": set(),
            "calls": {Call("fn_b()", ["arg"], {}, target=fn_b)},
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
        fn_a = Func("fn_a", ["a"], None, None)
        fn_b = Func("fn_b", ["b"], None, None)
        fn_c = Func("fn_c", ["c"], None, None)
        fn_a_ir = {
            "sets": set(),
            "gets": {Name("a.in_a", "a")},
            "dels": set(),
            "calls": {Call("fn_b()", ["a"], {}, target=fn_b)},
        }
        fn_b_ir = {
            "sets": set(),
            "gets": {Name("b.in_b", "b")},
            "dels": set(),
            "calls": {Call("fn_c()", ["b"], {}, target=fn_c)},
        }
        fn_c_ir = {
            "sets": set(),
            "gets": {Name("c.in_c", "c")},
            "dels": set(),
            "calls": {Call("fn_b()", [], {"b": "c"}, target=fn_b)},
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
        fn_a = Func("fn_a", ["a"], None, None)
        fn_b = Func("fn_b", ["b"], None, None)
        fn_a_ir = {
            "sets": set(),
            "gets": {Name("a.in_a", "a")},
            "dels": set(),
            "calls": {
                Call("fn_b()", ["a.attr"], {}, target=fn_b),
                Call("fn_b()", ["a.attr"], {}, target=fn_b),
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
        fn_a = Func("fn_a", ["a"], None, None)
        fn_b = Func("fn_b", ["b"], None, None)
        fn_a_ir = {
            "sets": set(),
            "gets": {Name("a.in_a", "a")},
            "dels": set(),
            "calls": {
                Call("fn_b()", ["a.attr_one"], {}, target=fn_b),
                Call("fn_b()", ["a.attr_two"], {}, target=fn_b),
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
        imports_ir = {
            "module": file_ir_from_dict(
                {
                    Func("act", ["arg"], None, None): {
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

        _i = Import("act", "module.act")
        _i.module_name = "module"
        _i.module_spec = mock.Mock()

        fn = Func("fn", ["ms"], None, None)
        fn_ir = {
            "sets": set(),
            "gets": set(),
            "dels": set(),
            "calls": {Call("act()", ["ms"], {}, target=_i)},
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
        _i_second = Import("second", "chained.second")
        _i_second.module_name = "chained"
        _i_second.module_spec = mock.Mock()

        imports_ir = {
            "module": file_ir_from_dict(
                {
                    Func("first", ["arrg"], None, None): {
                        "sets": set(),
                        "gets": set(),
                        "dels": set(),
                        "calls": {Call("second", ["arrg"], {}, target=_i_second)},
                    }
                }
            ),
            "chained": file_ir_from_dict(
                {
                    Func("second", ["blarg"], None, None): {
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

        _i_module = Import("first", "module.first")
        _i_module.module_name = "module"
        _i_module.module_spec = mock.Mock()

        fn = Func("fn", ["flarg"], None, None)
        fn_ir = {
            "sets": set(),
            "gets": set(),
            "dels": set(),
            "calls": {Call("first()", ["flarg"], {}, target=_i_module)},
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
        cls_inst_sm = Func("SomeClass.static", ["flarg"], None, None)
        cls_inst_sm_ir = {
            "sets": {
                Name("flarg.attr_in_static", "flarg"),
            },
            "gets": set(),
            "dels": set(),
            "calls": set(),
        }
        fn = Func("i_call_them", ["marg"], None, None)
        fn_ir = {
            "sets": {
                Name("instance"),
            },
            "gets": set(),
            "dels": set(),
            "calls": {
                Call("SomeClass()", ["instance", "marg"], {}, target=cls_inst),
                Call("SomeClass.static()", ["marg"], {}, target=cls_inst_sm),
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
