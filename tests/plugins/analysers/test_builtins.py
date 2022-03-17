import pytest

from rattr.analyser.context import Call, Func, Name, RootContext
from rattr.analyser.file import FileAnalyser
from rattr.plugins import plugins
from rattr.plugins.analysers.builtins import SortedAnalyser


class TestCustomFunctionAnalysers:
    @pytest.fixture(autouse=True)
    def apply_plugins(self):
        plugins.register(SortedAnalyser())

    def test_sorted_no_key(self, parse):
        _ast = parse(
            """
            def a_func(arg):
                sorted(arg)
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "gets": {
                    Name("arg"),
                },
                "sets": set(),
                "dels": set(),
                "calls": set(),
            }
        }

        assert results == expected

    def test_sorted_with_constant_key(self, parse):
        # Literal
        _ast = parse(
            """
            def a_func(arg):
                sorted(arg, key=1)
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "gets": {
                    Name("arg"),
                },
                "sets": set(),
                "dels": set(),
                "calls": set(),
            }
        }

        assert results == expected

        # Attribute
        _ast = parse(
            """
            def a_func(arg):
                sorted(arg, key=arg.attr)
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "gets": {
                    Name("arg"),
                    Name("arg.attr", "arg"),
                },
                "sets": set(),
                "dels": set(),
                "calls": set(),
            }
        }

        assert results == expected

    def test_sorted_key_is_callable(self, parse):
        # Via lambda
        _ast = parse(
            """
            def a_func(arg):
                sorted(arg, key=lambda a: key_func(a))

            def key_func(a):
                return a.b
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        a_func = Func("a_func", ["arg"], None, None)
        key_func = Func("key_func", ["a"], None, None)
        expected = {
            a_func: {
                "gets": {
                    Name("arg"),
                },
                "sets": set(),
                "dels": set(),
                "calls": {Call("key_func()", ["a"], {}, target=key_func)},
            },
            key_func: {
                "gets": {
                    Name("a.b", "a"),
                },
                "sets": set(),
                "dels": set(),
                "calls": set(),
            },
        }

        assert results == expected

    def test_sorted_key_is_attribute_or_element(self, parse):
        # Attribute
        _ast = parse(
            """
            def a_func(arg):
                sorted(arg, key=lambda a: a.attr)
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "gets": {
                    Name("arg"),
                    Name("arg.attr", "arg"),
                },
                "sets": set(),
                "dels": set(),
                "calls": set(),
            }
        }

        assert results == expected

        # Element
        _ast = parse(
            """
            def a_func(arg):
                sorted(arg, key=lambda a: a[0])
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "gets": {
                    Name("arg"),
                    Name("arg[]", "arg"),
                },
                "sets": set(),
                "dels": set(),
                "calls": set(),
            }
        }

        assert results == expected

        # Complex
        _ast = parse(
            """
            def a_func(arg):
                sorted(arg, key=lambda a: a[0].attr)
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "gets": {
                    Name("arg"),
                    Name("arg[].attr", "arg"),
                },
                "sets": set(),
                "dels": set(),
                "calls": set(),
            }
        }

        assert results == expected
