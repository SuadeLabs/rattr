from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from rattr.analyser.file import FileAnalyser
from rattr.models.context import compile_root_context
from rattr.models.ir import FileIr
from rattr.models.symbol import (
    Builtin,
    Call,
    CallArguments,
    CallInterface,
    Class,
    Func,
    Name,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests.shared import MakeRootContextFn, ParseFn, StateFn


@pytest.fixture(autouse=True)
def __set_current_file(state: StateFn) -> Iterator[None]:
    with state(current_file=Path(__file__)):
        yield


class TestFunctionAnalyser:
    def test_basic_function(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(arg):
                arg.sets_me = "value"
                return arg.gets_me
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))

        expected = FileIr(
            context=make_root_context([a_func], include_root_symbols=True),
            file_ir={
                a_func: {
                    "gets": {Name("arg.gets_me", "arg")},
                    "sets": {Name("arg.sets_me", "arg")},
                    "dels": set(),
                    "calls": set(),
                }
            },
        )

        assert results == expected

    def test_multiple_functions(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(arg):
                arg.sets_me = "value"
                return arg.gets_me

            def another_func(arg):
                arg.attr = "this function only sets"
                arg.attr_two = "see!"
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        another_func = Func(name="another_func", interface=CallInterface(args=("arg",)))

        expected = FileIr(
            context=make_root_context(
                [
                    a_func,
                    another_func,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "gets": {Name("arg.gets_me", "arg")},
                    "sets": {Name("arg.sets_me", "arg")},
                    "dels": set(),
                    "calls": set(),
                },
                another_func: {
                    "gets": set(),
                    "sets": {
                        Name("arg.attr", "arg"),
                        Name("arg.attr_two", "arg"),
                    },
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_conditional(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(arg):
                if debug:
                    return False
                return arg.attr == "target value"
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))

        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "gets": {
                        Name("debug"),
                        Name("arg.attr", "arg"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_nested_conditional(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(arg):
                if c1:
                    if c2:
                        return arg.foo
                return arg.bar
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))

        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "gets": {
                        Name("c1"),
                        Name("c2"),
                        Name("arg.foo", "arg"),
                        Name("arg.bar", "arg"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_nested_function(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        # NOTE Does not test function following, `arg` always named such
        ast_ = parse(
            """
            def a_func(arg):
                def inner(arg):
                    return arg.foo
                return inner(arg)
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        inner_symbol = Func(name="inner", interface=CallInterface(args=("arg",)))
        inner_symbol_call = Call(
            name="inner",
            args=CallArguments(args=("arg",), kwargs={}),
            target=inner_symbol,
        )

        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "gets": {
                        Name("arg"),
                        Name("arg.foo", "arg"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": {inner_symbol_call},
                },
            },
        )

        assert results == expected

    # def test_comprehensions(self, parse: ParseFn):
    #     ast_ = parse("""
    #         def list_comp(arg):
    #             return [a.prop for a in arg.iter]
    #     """)
    #     results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

    #     expected = {
    #         Func("list_comp", ["arg"], None, None): {
    #             "gets": {
    #                 # ...
    #             },
    #             "sets": set()
    #             "dels": set(),
    #             "calls": set(),
    #         },
    #     }

    #     assert results == expected

    def test_getattr_simple(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(arg):
                return getattr(arg, "attr")
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "gets": {Name("arg"), Name("arg.attr", "arg")},
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_getattr_nested(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(arg):
                return getattr(getattr(arg, "inner"), "outer")
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "gets": {
                        Name("arg"),
                        Name("arg.inner", "arg"),
                        Name("arg.inner.outer", "arg"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_getattr_nested_complex(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(arg):
                return getattr(getattr(arg.b[0], "inner"), "outer")
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "gets": {
                        Name("arg"),
                        Name("arg.b[]", "arg"),
                        Name("arg.b[].inner", "arg"),
                        Name("arg.b[].inner.outer", "arg"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_hasattr_simple(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(arg):
                return hasattr(arg, "attr")
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "gets": {Name("arg"), Name("arg.attr", "arg")},
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_hasattr_nested(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(arg):
                return hasattr(hasattr(arg, "inner"), "outer")
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "gets": {
                        Name("arg"),
                        Name("arg.inner", "arg"),
                        Name("arg.inner.outer", "arg"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_hasattr_nested_complex(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(arg):
                return hasattr(hasattr(arg.b[0], "inner"), "outer")
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "gets": {
                        Name("arg"),
                        Name("arg.b[]", "arg"),
                        Name("arg.b[].inner", "arg"),
                        Name("arg.b[].inner.outer", "arg"),
                    },
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_setattr_simple(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(arg):
                setattr(arg, "attr", "value")
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "gets": {Name("arg")},
                    "sets": {Name("arg.attr", "arg")},
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_setattr_complex(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(arg):
                return setattr(arg.b[0], "attr", "value")
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "gets": {
                        Name("arg"),
                        Name("arg.b[]", "arg"),
                    },
                    "sets": {Name("arg.b[].attr", "arg")},
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_delattr_simple(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(arg):
                delattr(arg, "attr")
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "gets": {Name("arg")},
                    "sets": set(),
                    "dels": {Name("arg.attr", "arg")},
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_delattr_complex(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(arg):
                return delattr(arg.b[0], "attr")
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "gets": {
                        Name("arg"),
                        Name("arg.b[]", "arg"),
                    },
                    "sets": set(),
                    "dels": {Name("arg.b[].attr", "arg")},
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_format_simple(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        constant: str,
    ):
        ast_ = parse(
            """
            def a_func(arg):
                return format(arg, "b")
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        format_builtin = Builtin(name="format")
        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        format_call = Call(
            name="format()",
            args=CallArguments(args=("arg", constant)),
            target=format_builtin,
        )

        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "gets": {Name("arg")},
                    "sets": set(),
                    "dels": set(),
                    "calls": {format_call},
                },
            },
        )

        assert results == expected

    def test_format_complex(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        constant: str,
    ):
        ast_ = parse(
            """
            def a_func(arg):
                return format(getattr(arg, "attr"), "b")
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        format_builtin = Builtin(name="format")
        a_func = Func(name="a_func", interface=CallInterface(args=("arg",)))
        format_call = Call(
            name="format()",
            args=CallArguments(args=("arg.attr", constant)),
            target=format_builtin,
        )

        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "gets": {Name("arg"), Name("arg.attr", "arg")},
                    "sets": set(),
                    "dels": set(),
                    "calls": {format_call},
                },
            },
        )

        assert results == expected

    def test_lambda(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            global_lamb = lambda x: x.attr

            def func_one(arg):
                return global_lamb(arg)

            def func_two(arg):
                return map(lambda x: x*x, [1, 2, 3])
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        func_one = Func(name="func_one", interface=CallInterface(args=("arg",)))
        func_two = Func(name="func_two", interface=CallInterface(args=("arg",)))
        global_lamb = Func(name="global_lamb", interface=CallInterface(args=("x",)))
        global_lamb_call = Call(
            name="global_lamb()",
            args=CallArguments(args=("arg",)),
            target=global_lamb,
        )
        map_symbol = Builtin("map")
        map_symbol_call = Call(
            name="map()",
            args=CallArguments(args=("@Lambda", "@List")),
            target=map_symbol,
        )

        expected = FileIr(
            context=make_root_context(
                [
                    global_lamb,
                    func_one,
                    func_two,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                global_lamb: {
                    "gets": {Name("x.attr", "x")},
                    "sets": set(),
                    "dels": set(),
                    "calls": set(),
                },
                func_one: {
                    "gets": {Name("arg")},
                    "sets": set(),
                    "dels": set(),
                    "calls": {global_lamb_call},
                },
                func_two: {
                    "gets": {Name("x")},
                    "sets": set(),
                    "dels": set(),
                    "calls": {map_symbol_call},
                },
            },
        )

        assert results == expected

    def test_class_init(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            class ClassName:
                def __init__(self, arg):
                    self.attr = arg

            def a_func(blarg):
                thing = ClassName(blarg)
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        cls = Class(name="ClassName", interface=CallInterface(args=("self", "arg")))
        cls_call = Call(
            "ClassName()",
            args=CallArguments(args=("thing", "blarg")),
            target=cls,
        )
        a_func = Func(name="a_func", interface=CallInterface(args=("blarg",)))

        expected = FileIr(
            context=make_root_context(
                [
                    cls,
                    a_func,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                cls: {
                    "sets": {Name("self.attr", "self")},
                    "gets": {Name("arg")},
                    "dels": set(),
                    "calls": set(),
                },
                a_func: {
                    "sets": {Name("thing")},
                    "gets": {Name("blarg")},
                    "dels": set(),
                    "calls": {cls_call},
                },
            },
        )

        assert results == expected

    def test_return_implicit_none(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(blarg):
                return
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("blarg",)))
        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "sets": set(),
                    "gets": set(),
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_return_literal(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(blarg):
                return 4
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("blarg",)))
        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "sets": set(),
                    "gets": set(),
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_return_local_variable(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(blarg):
                return blarg.attr
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("blarg",)))
        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "sets": set(),
                    "gets": {Name("blarg.attr", "blarg")},
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_return_tuple_without_class_call(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def a_func(blarg):
                return blarg.attr, 1, a_call(blarg.another_attr)
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("blarg",)))
        a_call = Call(
            name="a_call",
            args=CallArguments(args=("blarg.another_attr",)),
            target=None,
        )

        expected = FileIr(
            context=make_root_context(
                [a_func],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "sets": set(),
                    "gets": {
                        Name("blarg.attr", "blarg"),
                        Name("blarg.another_attr", "blarg"),
                    },
                    "dels": set(),
                    "calls": {a_call},
                },
            },
        )

        assert results == expected

    def test_return_class_call(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        constant: str,
    ):
        ast_ = parse(
            """
            class MyEnum(Enum):
                first = "one"
                second = "two"

            def a_func(blarg):
                return MyEnum("one")
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("blarg",)))
        my_enum_symbol = Class(
            name="MyEnum",
            interface=CallInterface(args=("self", "_id")),
        )
        my_enum_first = Name("MyEnum.first", "MyEnum")
        my_enum_second = Name("MyEnum.second", "MyEnum")
        my_enum_call = Call(
            name="MyEnum",
            args=CallArguments(args=("@ReturnValue", constant)),
            target=my_enum_symbol,
        )

        expected = FileIr(
            context=make_root_context(
                [
                    a_func,
                    my_enum_symbol,
                    my_enum_first,
                    my_enum_second,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "sets": set(),
                    "gets": set(),
                    "dels": set(),
                    "calls": {my_enum_call},
                },
                my_enum_symbol: {
                    "sets": set(),
                    "gets": {my_enum_first, my_enum_second},
                    "calls": set(),
                    "dels": set(),
                },
            },
        )

        assert (
            results.context.symbol_table._symbols
            == expected.context.symbol_table._symbols
        )
        assert results == expected

    def test_return_tuple_with_class(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        constant: str,
    ):
        ast_ = parse(
            """
            class MyEnum(Enum):
                first = "one"
                second = "two"

            def a_func(blarg):
                return 1, MyEnum("one"), blarg.attr
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        a_func = Func(name="a_func", interface=CallInterface(args=("blarg",)))
        my_enum_symbol = Class(
            name="MyEnum",
            interface=CallInterface(args=("self", "_id")),
        )
        my_enum_first = Name("MyEnum.first", "MyEnum")
        my_enum_second = Name("MyEnum.second", "MyEnum")
        my_enum_call = Call(
            name="MyEnum",
            args=CallArguments(args=("@ReturnValue", constant)),
            target=my_enum_symbol,
        )

        expected = FileIr(
            context=make_root_context(
                [
                    a_func,
                    my_enum_symbol,
                    my_enum_first,
                    my_enum_second,
                ],
                include_root_symbols=True,
            ),
            file_ir={
                a_func: {
                    "sets": set(),
                    "gets": {Name("blarg.attr", "blarg")},
                    "dels": set(),
                    "calls": {my_enum_call},
                },
                my_enum_symbol: {
                    "sets": set(),
                    "gets": {my_enum_first, my_enum_second},
                    "calls": set(),
                    "dels": set(),
                },
            },
        )

        assert results == expected

    def test_walrus(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def fn(arg):
                if (a := arg.attr):
                    return a
                else:
                    return (b := arg.another_attr)
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        fn = Func(name="fn", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context([fn], include_root_symbols=True),
            file_ir={
                fn: {
                    "sets": {
                        Name("a"),
                        Name("b"),
                    },
                    "gets": {
                        Name("a"),
                        Name("arg.attr", "arg"),
                        Name("arg.another_attr", "arg"),
                    },
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_walrus_basic(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def fn(arg):
                thing = (a, b := arg.attr)
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        fn = Func(name="fn", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context([fn], include_root_symbols=True),
            file_ir={
                fn: {
                    "sets": {
                        Name("b"),
                        Name("thing"),
                    },
                    "gets": {
                        Name("a"),
                        Name("arg.attr", "arg"),
                    },
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_walrus_multiple_assignment(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def fn(arg):
                x, y = (a, b := c)
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        fn = Func(name="fn", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context([fn], include_root_symbols=True),
            file_ir={
                fn: {
                    "sets": {
                        Name("x"),
                        Name("y"),
                        Name("b"),
                    },
                    "gets": {
                        Name("a"),
                        Name("c"),
                    },
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_walrus_lambda(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
        capfd: pytest.CaptureFixture[str],
    ):
        ast_ = parse(
            """
            def fn(arg):
                other = (name := lambda *a, **k: a.attr)
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        _, stderr = capfd.readouterr()
        assert "unable to unbind lambdas defined in functions" in stderr

        fn = Func(name="fn", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context([fn], include_root_symbols=True),
            file_ir={
                fn: {
                    "sets": {
                        Name("other"),
                        Name("name"),
                    },
                    "gets": {
                        Name("a.attr", "a"),
                    },
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_walrus_multiple_assign_with_lambda(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def fn(arg):
                other = (alpha, beta := lambda *a, **k: a.attr)
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        fn = Func(name="fn", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context([fn], include_root_symbols=True),
            file_ir={
                fn: {
                    "sets": {
                        Name("other"),
                        Name("beta"),
                    },
                    "gets": {
                        Name("alpha"),
                        Name("a.attr", "a"),
                    },
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected

    def test_walrus_multiple_assign_with_lambda_as_list(
        self,
        parse: ParseFn,
        make_root_context: MakeRootContextFn,
    ):
        ast_ = parse(
            """
            def fn(arg):
                other = [alpha, beta := lambda *a, **k: a.attr]
            """
        )
        results = FileAnalyser(ast_, compile_root_context(ast_)).analyse()

        fn = Func(name="fn", interface=CallInterface(args=("arg",)))
        expected = FileIr(
            context=make_root_context([fn], include_root_symbols=True),
            file_ir={
                fn: {
                    "sets": {
                        Name("other"),
                        Name("beta"),
                    },
                    "gets": {
                        Name("alpha"),
                        Name("a.attr", "a"),
                    },
                    "dels": set(),
                    "calls": set(),
                },
            },
        )

        assert results == expected
