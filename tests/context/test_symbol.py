from rattr.analyser.context.symbol import (
    Call,
    Class,
    Func,
    Import,
    Name,
    Symbol,
    find_spec,
    get_module_name_and_spec,
    get_possible_module_names,
    parse_call,
    parse_name,
)


class TestSymbol:
    def test_eq(self):
        assert Name("a") == Name("a")
        assert Name("a") == Name("a", "a")
        assert Name("a") != "a"
        assert Name("a") != Name("b")
        assert Name("a") != Import("a")

    def test_hash(self):
        assert hash(Name("a")) == hash(Name("a"))
        assert hash(Name("a")) == hash(Name("a", "a"))
        assert hash(Name("a")) != hash(Name("b"))
        assert hash(Name("a")) != hash(Import("a"))

    def test_is(self):
        symbols = [
            Name("a"),
            Import("a"),
            Func("a()", [], None, None),
            Call("a()", [], {}),
            Class("a", None, None, None),
        ]
        symbol_types = [
            [Import, Func, Call, Class],  # noqa
            [Name, Func, Call, Class],  # noqa
            [Name, Import, Call, Class],  # noqa
            [Name, Import, Func, Class],  # noqa
            [
                Name,
                Import,
                Func,
                Call,
            ],  # noqa
        ]

        for symbol in symbols:
            assert symbol._is(Symbol)

        for s, _types in zip(symbols, symbol_types):
            for _type in _types:
                assert not s._is(_type)

        assert symbols[0]._is(Name)
        assert symbols[1]._is(Import)
        assert symbols[2]._is(Func)
        assert symbols[3]._is(Call)
        assert symbols[4]._is(Class)

    def test_name(self):
        assert Name("a") == Name("a", "a")

        a = Name("a")
        assert a.name == "a"
        assert a.basename == "a"

        b_dot_attr = Name("b.attr", "b")
        assert b_dot_attr.name == "b.attr"
        assert b_dot_attr.basename == "b"

    def test_import(self):
        assert Import("a") == Import("a", "a")

        # Unresolved import
        a = Import("a")
        assert a.name == "a"
        assert a.qualified_name == "a"
        assert a.module_name is None
        assert a.module_spec is None

        # Unresolved from import
        b_dot_func = Import("func", "b.func")
        assert b_dot_func.name == "func"
        assert b_dot_func.qualified_name == "b.func"
        assert b_dot_func.module_name is None
        assert b_dot_func.module_spec is None

        # Resolved stdlib import
        stdlib = Import("math")
        assert stdlib.name == "math"
        assert stdlib.qualified_name == "math"
        assert stdlib.module_name == "math"
        assert stdlib.module_spec == find_spec("math")

        # Resolved stdlib from import
        stdlib = Import("pi", "math.pi")
        assert stdlib.name == "pi"
        assert stdlib.qualified_name == "math.pi"
        assert stdlib.module_name == "math"
        assert stdlib.module_spec == find_spec("math")

        # Resolved, dotted stdlib from import
        stdlib = Import("join", "os.path.join")
        assert stdlib.name == "join"
        assert stdlib.qualified_name == "os.path.join"
        assert stdlib.module_name == "os.path"
        assert stdlib.module_spec == find_spec("os.path")

    def test_func(self):
        # def fn()
        fn = Func("fn", [], None, None)
        assert fn.name == "fn"
        assert fn.args == []
        assert fn.vararg is None
        assert fn.kwarg is None
        assert not fn.is_async

        # async def async_fn(a, b='val', *c, **d)
        async_fn = Func("async_fn", ["a", "b"], "c", "d", is_async=True)
        assert async_fn.name == "async_fn"
        assert async_fn.args == ["a", "b"]
        assert async_fn.vararg == "c"
        assert async_fn.kwarg == "d"
        assert async_fn.is_async

    def test_call(self):
        # fn()
        call = Call("fn", [], {})
        assert call.name == "fn"
        assert call.args == []
        assert call.kwargs == {}

        # fn(a, b, c=d)
        call = Call("fn", ["a", "b"], {"c": "d"})
        assert call.name == "fn"
        assert call.args == ["a", "b"]
        assert call.kwargs == {"c": "d"}

    def test_class(self):
        # class ClassName
        # Always initialised with None's (outside of tests, for convenience)
        # None's imply that initialiser has not been seen
        cls = Class("ClassName", None, None, None)
        assert cls.name == "ClassName"
        assert cls.args is None
        assert cls.vararg is None
        assert cls.kwarg is None


class TestSymbolUtils:
    def test_parse_name(self):
        assert parse_name("var") == Name("var")
        assert parse_name("var.attr") == Name("var.attr", "var")

        assert parse_name("*var") == Name("*var", "var")
        assert parse_name("*var.attr") == Name("*var.attr", "var")

        complex_name = "*var.mth().res[].attr"
        assert parse_name(complex_name) == Name(complex_name, "var")

    def test_parse_call(self):
        pos, named = [], {}
        assert parse_call("func()", (pos, named)) == Call("func()", pos, named)

        pos, named = ["a", "b", "c"], {"d": "e", "f": "g"}
        assert parse_call("func()", (pos, named)) == Call("func()", pos, named)

        # Allow omit brackets
        pos, named = [], {}
        assert parse_call("func", (pos, named)) == Call("func()", pos, named)

    def test_get_possible_module_names(self):
        expected = ["a.b.c.d", "a.b.c", "a.b", "a"]
        assert get_possible_module_names("a.b.c.d") == expected

        expected = ["os.path.join", "os.path", "os"]
        assert get_possible_module_names("os.path.join") == expected

        expected = [""]
        assert get_possible_module_names("") == expected

        expected = ["a_name_without_dots"]
        assert get_possible_module_names("a_name_without_dots") == expected

    def test_get_module_name_and_spec(self):
        assert get_module_name_and_spec("i.am.not.a.module") == (None, None)

        expected = ("math", find_spec("math"))
        assert get_module_name_and_spec("math") == expected
        assert get_module_name_and_spec("math.pi") == expected

        expected = ("os", find_spec("os"))
        assert get_module_name_and_spec("os") == expected

        expected = ("os.path", find_spec("os.path"))
        assert get_module_name_and_spec("os.path") == expected

        assert get_module_name_and_spec("os") != get_module_name_and_spec("os.path")

        m = "rattr.analyser"
        expected = (m, find_spec(m))
        assert get_module_name_and_spec(m) == expected

        m = "rattr.analyser.util"
        expected = (m, find_spec(m))
        assert get_module_name_and_spec(f"{m}.get_module_spec") == expected
