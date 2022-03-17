from unittest import mock

import pytest

from rattr.analyser.context import Builtin, Call, Func, Import, Name
from rattr.analyser.context.symbol import Class
from rattr.analyser.ir_dag import (
    IrDagNode,
    construct_swap,
    get_callee_target,
    partially_unbind,
    partially_unbind_name,
)


class TestIrDag_Utils:
    def test_get_callee_target(self):
        fn_a = Func("fn_a", [], None, None)
        fn_b = Func("fn_b", [], None, None)
        cls_a = Class("ClassA", ["self", "arg"], None, None)
        fn_a_ir = {
            "sets": {Name("a"), Name("b.attr", "b")},
            "gets": {Name("c")},
            "dels": set(),
            "calls": set(),
        }
        fn_b_ir = {
            "sets": set(),
            "gets": set(),
            "dels": {Name("a")},
            "calls": set(),
        }
        cls_a_ir = {
            "sets": {Name("self.field", "self")},
            "gets": {Name("arg.attr", "arg")},
            "dels": set(),
            "calls": set(),
        }
        file_ir = {
            fn_a: fn_a_ir,
            fn_b: fn_b_ir,
            cls_a: cls_a_ir,
        }

        # No callee target
        broken_call = Call("some_func()", [], {}, target=None)
        assert get_callee_target(broken_call, file_ir, {}) == (None, None)

        # Callee is a builtin
        builtin = Call("max()", [], {}, Builtin("max", has_affect=False))
        assert get_callee_target(builtin, file_ir, {}) == (None, None)

        # Normal -- `fn_a`
        fn_a_call = Call("fn_a()", [], {}, target=fn_a)
        assert get_callee_target(fn_a_call, file_ir, {}) == (fn_a, fn_a_ir)

        # Normal -- `fn_b`
        fn_b_call = Call("fn_b()", [], {}, target=fn_b)
        assert get_callee_target(fn_b_call, file_ir, {}) == (fn_b, fn_b_ir)

        # Normal -- class initialiser
        cls_a_call = Call("ClassA()", ["a"], {}, target=cls_a)
        assert get_callee_target(cls_a_call, file_ir, {}) == (cls_a, cls_a_ir)

        # Non-existent
        fake_call = Call("not_a_real_function()", [], {})
        assert get_callee_target(fake_call, file_ir, {}) == (None, None)

    @pytest.mark.pypy()
    def test_get_callee_target_callee_in_stdlib(self):
        fn_a = Func("fn_a", [], None, None)
        fn_b = Func("fn_b", [], None, None)
        cls_a = Class("ClassA", ["self", "arg"], None, None)
        fn_a_ir = {
            "sets": {Name("a"), Name("b.attr", "b")},
            "gets": {Name("c")},
            "dels": set(),
            "calls": set(),
        }
        fn_b_ir = {
            "sets": set(),
            "gets": set(),
            "dels": {Name("a")},
            "calls": set(),
        }
        cls_a_ir = {
            "sets": {Name("self.field", "self")},
            "gets": {Name("arg.attr", "arg")},
            "dels": set(),
            "calls": set(),
        }
        file_ir = {
            fn_a: fn_a_ir,
            fn_b: fn_b_ir,
            cls_a: cls_a_ir,
        }

        # Callee is in stdlib
        stdlib = Call("sin()", [], {}, target=Import("sin", "math.sin"))
        assert stdlib.target.module_name == "math"
        assert get_callee_target(stdlib, file_ir, {}) == (None, None)

    def test_get_callee_target_imported_function(self, file_ir_from_dict, capfd):
        # TODO Imported class/method
        fn = Func("fn", [], None, None)
        fn_ir = {"sets": set(), "gets": set(), "dels": set(), "calls": set()}
        imports_ir = {"module": file_ir_from_dict({fn: fn_ir})}

        # Callee is imported
        _i = Import("fn", "module.fn")
        _i.module_name = "module"
        _i.module_spec = mock.Mock()
        call = Call("fn()", [], {}, target=_i)
        assert get_callee_target(call, {}, imports_ir) == (fn, fn_ir)

        # Callee is imported but not defined in source
        _i = Import("nope", "module.nope")
        _i.module_name = "module"
        _i.module_spec = mock.Mock()
        call = Call("nope()", [], {}, target=_i)

        assert get_callee_target(call, {}, imports_ir) == (None, None)

        output, _ = capfd.readouterr()
        assert "unable to resolve call to 'nope' in import" in output

        # Callee module and target not found
        _i = Import("nah", "noway.nah")
        _i.module_name = "noway"
        _i.module_spec = mock.Mock()
        call = Call("nah()", [], {}, target=_i)

        with pytest.raises(ImportError):
            get_callee_target(call, {}, imports_ir)

    def test_partially_unbind_name(self):
        # On basic name
        foo, star_foo = Name("foo"), Name("*foo", "foo")

        assert partially_unbind_name(foo, "foo") == foo
        assert partially_unbind_name(star_foo, "foo") == star_foo

        assert partially_unbind_name(foo, "bar") == Name("bar")
        assert partially_unbind_name(star_foo, "bar") == Name("*bar", "bar")

        # On complex name
        comp = Name("comp.attr.m().res_attr[].item", "comp")
        star_comp = Name("*comp.attr.m().res_attr[].item", "comp")

        assert partially_unbind_name(comp, "comp") == comp
        assert partially_unbind_name(star_comp, "comp") == star_comp

        expected_comp = Name("bar.attr.m().res_attr[].item", "bar")
        expected_star_comp = Name("*bar.attr.m().res_attr[].item", "bar")

        assert partially_unbind_name(comp, "bar") == expected_comp
        assert partially_unbind_name(star_comp, "bar") == expected_star_comp

    def test_partially_unbind(self):
        empty_func_ir = {
            "sets": set(),
            "gets": set(),
            "dels": set(),
            "calls": set(),
        }
        func_ir = {
            "sets": {
                Name("a"),
                Name("a.attr", "a"),
            },
            "gets": {
                Name("arg"),
                Name("arg.mth().res_attr[].value", "arg"),
            },
            "dels": {
                Name("bob"),
                Name("*dob", "dob"),
            },
            "calls": {Call("callee()", [], {})},
        }

        # No names, no swaps
        assert partially_unbind(empty_func_ir, {}) == empty_func_ir

        # No names, w/ swaps
        assert partially_unbind(empty_func_ir, {"a": "b"}) == empty_func_ir

        # No swaps
        assert partially_unbind(func_ir, {}) == func_ir

        # Only relevant swaps #1
        expected = {
            "sets": {
                Name("b"),
                Name("b.attr", "b"),
            },
            "gets": {
                Name("arg"),
                Name("arg.mth().res_attr[].value", "arg"),
            },
            "dels": {
                Name("bob"),
                Name("*dob", "dob"),
            },
            "calls": {Call("callee()", [], {})},
        }
        swaps = {"a": "b"}

        assert partially_unbind(func_ir, swaps) == expected

        # Only relevant swaps #2
        expected = {
            "sets": {
                Name("a"),
                Name("a.attr", "a"),
            },
            "gets": {
                Name("barg"),
                Name("barg.mth().res_attr[].value", "barg"),
            },
            "dels": {
                Name("bobby"),
                Name("*dob", "dob"),
            },
            "calls": {Call("callee()", [], {})},
        }
        swaps = {
            "arg": "barg",
            "bob": "bobby",
        }

        assert partially_unbind(func_ir, swaps) == expected

        # Mixed swaps
        expected = {
            "sets": {
                Name("a"),
                Name("a.attr", "a"),
            },
            "gets": {
                Name("arg"),
                Name("arg.mth().res_attr[].value", "arg"),
            },
            "dels": {
                Name("bob"),
                Name("*dib", "dib"),
            },
            "calls": {Call("callee()", [], {})},
        }
        swaps = {"dob": "dib", "xyz": "zyx"}

        assert partially_unbind(func_ir, swaps) == expected

        # Regression
        func_ir = {
            "sets": {
                Name(name="arg_b.set_in_fn_b", basename="arg_b"),
            },
            "gets": set(),
            "dels": set(),
            "calls": set(),
        }
        expected = {
            "sets": {
                Name(name="arg.set_in_fn_b", basename="arg"),
            },
            "gets": set(),
            "dels": set(),
            "calls": set(),
        }
        swaps = {"arg_b": "arg"}

        assert partially_unbind(func_ir, swaps) == expected

    def test_construct_swap(self, capfd):
        # No args in both
        fn_def = Func("fn", [], None, None)
        fn_call = Call("fn", [], {})

        expected = {}

        assert construct_swap(fn_def, fn_call) == expected

        # Positional
        fn_def = Func("fn", ["a", "b"], None, None)
        fn_call = Call("fn", ["c", "d"], {})

        expected = {"a": "c", "b": "d"}

        assert construct_swap(fn_def, fn_call) == expected

        # Keyword
        fn_def = Func("fn", ["a", "b"], None, None)
        fn_call = Call("fn", [], {"a": "not_a", "b": "not_b"})

        expected = {"a": "not_a", "b": "not_b"}

        assert construct_swap(fn_def, fn_call) == expected

        # Mixed
        fn_def = Func("fn", ["a", "b", "c", "d"], None, None)
        fn_call = Call("fn", ["not_a", "not_b"], {"d": "not_d", "c": "not_c"})

        expected = {"a": "not_a", "b": "not_b", "c": "not_c", "d": "not_d"}

        assert construct_swap(fn_def, fn_call) == expected

        # Complex mixed w/ default on 'e'
        fn_def = Func("fn", ["a", "b", "c", "d", "e"], None, None)
        fn_call = Call("fn", ["not_a", "not_b"], {"d": "not_d", "c": "not_c"})

        expected = {"a": "not_a", "b": "not_b", "c": "not_c", "d": "not_d"}

        assert construct_swap(fn_def, fn_call) == expected

        # No matches
        fn_def = Func("fn", ["a", "b"], None, None)
        fn_call = Call("fn", [], {"c": "no_match", "d": "no_match"})

        expected = {}

        assert construct_swap(fn_def, fn_call) == expected

        output, _ = capfd.readouterr()

        assert "unexpected named arguments" in output

        # Provide as positional and named
        fn_def = Func("fn", ["a"], None, None)
        fn_call = Call("fn", ["not_a"], {"a": "not_a"})

        with mock.patch("sys.exit") as _exit:
            construct_swap(fn_def, fn_call)

        assert _exit.call_count == 1


class TestIrDagNode:

    # NOTE
    #   TestIrDagNode.simplify tested in the test for `results.py`'s
    #   `generate_results_from_ir` function as the tests would be almost
    #   identical either way

    def test_populate(self):
        fn_a = Func("fn_a", ["a"], None, None)
        fn_b = Func("fn_b", ["b"], None, None)
        fn_c = Func("fn_c", ["c"], None, None)
        fn_d = Func("fn_d", ["d"], None, None)
        fn_a_ir = {
            "sets": {Name("a")},
            "gets": set(),
            "dels": set(),
            "calls": {Call("fn_b()", ["a"], {}, target=fn_b)},
        }
        fn_b_ir = {
            "sets": {Name("b")},
            "gets": set(),
            "dels": set(),
            "calls": {
                Call("fn_c()", ["b"], {}, target=fn_c),
                Call("fn_d()", ["b"], {}, target=fn_d),
            },
        }
        fn_c_ir = {
            "sets": {Name("c")},
            "gets": set(),
            "dels": set(),
            "calls": set(),
        }
        fn_d_ir = {
            "sets": {Name("d")},
            "gets": set(),
            "dels": set(),
            "calls": set(),
        }
        file_ir = {
            fn_a: fn_a_ir,
            fn_b: fn_b_ir,
            fn_c: fn_c_ir,
            fn_d: fn_d_ir,
        }

        A = IrDagNode(None, fn_a, fn_a_ir, file_ir, dict())
        A.populate()

        B_in_A = A.children[0]

        # C and D can be either way around as it is a set
        if B_in_A.children[0].func.name == fn_c.name:
            C_in_A = B_in_A.children[0]
            D_in_A = B_in_A.children[1]
        else:
            C_in_A = B_in_A.children[1]
            D_in_A = B_in_A.children[0]

        # A
        assert A.call is None
        assert A.func == fn_a
        assert A.func_ir == fn_a_ir
        assert A.file_ir == file_ir
        assert len(A.children) == 1

        # B
        assert B_in_A.call == Call("fn_b()", ["a"], {}, target=fn_b)
        assert B_in_A.func == fn_b
        assert B_in_A.func_ir == fn_b_ir
        assert B_in_A.file_ir == file_ir
        assert len(B_in_A.children) == 2

        # C
        assert C_in_A.call == Call("fn_c()", ["b"], {}, target=fn_c)
        assert C_in_A.func == fn_c
        assert C_in_A.func_ir == fn_c_ir
        assert C_in_A.file_ir == file_ir
        assert len(C_in_A.children) == 0

        # D
        assert D_in_A.call == Call("fn_d()", ["b"], {}, target=fn_d)
        assert D_in_A.func == fn_d
        assert D_in_A.func_ir == fn_d_ir
        assert D_in_A.file_ir == file_ir
        assert len(D_in_A.children) == 0

    def test_on_undefined(self, capfd):
        fn_a = Func("fn_a", ["a"], None, None)
        fn_a_ir = {
            "sets": {Name("a")},
            "gets": set(),
            "dels": set(),
            "calls": {
                Call("fn_b()", ["a"], {}),
                Call("some_undefined_func()", [], {}),
            },
        }
        fn_b = Func("fn_b", ["b"], None, None)
        fn_b_ir = {
            "sets": {Name("b")},
            "gets": set(),
            "dels": set(),
            "calls": {
                Call("some_other_undefined_func()", [], {}),
            },
        }
        file_ir = {
            fn_a: fn_a_ir,
            fn_b: fn_b_ir,
        }

        A = IrDagNode(None, fn_a, fn_a_ir, file_ir, {})

        # NOTE Error is already logged by analyser, thus nothing should happen
        A.populate()
        A.simplify()

        output, _ = capfd.readouterr()

        assert output == ""

    def test_populate_on_stdlib(self, capfd):
        fn_a = Func("fn_a", ["a"], None, None)
        fn_a_ir = {
            "sets": {Name("a")},
            "gets": set(),
            "dels": set(),
            "calls": {
                Call("os.path.join()", [], {}),
                Call("math.max()", [], {}),
            },
        }
        file_ir = {
            fn_a: fn_a_ir,
        }

        A = IrDagNode(None, fn_a, fn_a_ir, file_ir, dict())
        A.populate()

        output, _ = capfd.readouterr()

        assert output == ""

    def test_populate_ignore_builtins(self, capfd):
        fn_a = Func("fn_a", ["a"], None, None)
        fn_a_ir = {
            "sets": {Name("a")},
            "gets": set(),
            "dels": set(),
            "calls": {
                Call("max()", [], {}),
                Call("enumerate()", [], {}),
            },
        }
        file_ir = {
            fn_a: fn_a_ir,
        }

        A = IrDagNode(None, fn_a, fn_a_ir, file_ir, dict())
        A.populate()

        output, _ = capfd.readouterr()

        assert output == ""

    def test_populate_ignore_seen(self):
        fn_a = Func("fn_a", ["a"], None, None)
        fn_b = Func("fn_b", ["b"], None, None)
        fn_c = Func("fn_c", ["c"], None, None)
        fn_a_ir = {
            "sets": {Name("a")},
            "gets": set(),
            "dels": set(),
            "calls": {
                Call("fn_a()", ["a"], {}, target=fn_a),
                Call("fn_b()", ["a"], {}, target=fn_b),
            },
        }
        fn_b_ir = {
            "sets": {Name("b")},
            "gets": set(),
            "dels": set(),
            "calls": {
                Call("fn_a()", ["b"], {}, target=fn_a),
                Call("fn_c()", ["b"], {}, target=fn_c),
            },
        }
        fn_c_ir = {
            "sets": {Name("b")},
            "gets": set(),
            "dels": set(),
            "calls": {
                Call("fn_b()", ["c"], {}, target=fn_b),
            },
        }
        file_ir = {
            fn_a: fn_a_ir,
            fn_b: fn_b_ir,
            fn_c: fn_c_ir,
        }

        A = IrDagNode(None, fn_a, fn_a_ir, file_ir, dict())
        A.populate()

        # Can be either way around as it is a set
        if A.children[0].func.name == fn_b.name:
            B_in_A = A.children[0]
        else:
            B_in_A = A.children[1]

        # Can be either way around as it is a set
        if B_in_A.children[0].func.name == fn_c.name:
            C_in_A = B_in_A.children[0]
        else:
            C_in_A = B_in_A.children[1]

        # A
        assert A.call is None
        assert A.func == fn_a
        assert A.func_ir == fn_a_ir
        assert A.file_ir == file_ir
        assert len(A.children) == 2

        # B
        assert B_in_A.call == Call("fn_b()", ["a"], {}, target=fn_b)
        assert B_in_A.func == fn_b
        assert B_in_A.func_ir == fn_b_ir
        assert B_in_A.file_ir == file_ir
        assert len(B_in_A.children) == 2

        # C
        assert C_in_A.call == Call("fn_c()", ["b"], {}, target=fn_c)
        assert C_in_A.func == fn_c
        assert C_in_A.func_ir == fn_c_ir
        assert C_in_A.file_ir == file_ir
        assert len(C_in_A.children) == 1
