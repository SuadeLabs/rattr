import pytest

from rattr.analyser.context import Builtin, Call, Func, Name, RootContext
from rattr.analyser.file import FileAnalyser
from rattr.plugins import plugins
from rattr.plugins.analysers.collections import DefaultDictAnalyser


class TestCustomCollectionsAnalysers:
    @pytest.fixture(autouse=True)
    def apply_plugins(self):
        plugins.register(DefaultDictAnalyser())

    def test_defaultdict_no_factory(self, parse):
        _ast = parse(
            """
            def a_func(arg):
                d = defaultdict()
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "gets": set(),
                "sets": {
                    Name("d"),
                },
                "dels": set(),
                "calls": set(),
            }
        }

        assert results == expected

    def test_defaultdict_named_factory(self, parse):
        _ast = parse(
            """
            def a_func(arg):
                d = defaultdict(factory)

            def factory():
                return hello.results
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        a_func = Func("a_func", ["arg"], None, None)
        factory = Func("factory", [], None, None)
        expected = {
            a_func: {
                "gets": set(),
                "sets": {
                    Name("d"),
                },
                "dels": set(),
                "calls": {Call("factory()", [], {}, target=factory)},
            },
            factory: {
                "gets": {
                    Name("hello.results", "hello"),
                },
                "sets": set(),
                "dels": set(),
                "calls": set(),
            },
        }

        assert results == expected

    def test_defaultdict_lambda_factory(self, parse):
        # Lambda to literal
        _ast = parse(
            """
            def a_func(arg):
                d = defaultdict(lambda: 0)
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "gets": set(),
                "sets": {
                    Name("d"),
                },
                "dels": set(),
                "calls": set(),
            }
        }

        print(results)
        print(expected)
        assert results == expected

        # Lambda to attr
        _ast = parse(
            """
            def a_func(arg):
                d = defaultdict(lambda: arg.attr)
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        expected = {
            Func("a_func", ["arg"], None, None): {
                "gets": {Name("arg.attr", "arg")},
                "sets": {
                    Name("d"),
                },
                "dels": set(),
                "calls": set(),
            }
        }

        print(results)
        print(expected)
        assert results == expected

    def test_defaultdict_nested_factory(self, parse):
        _ast = parse(
            """
            def a_func(arg):
                d = defaultdict(defaultdict(list))
        """
        )
        results = FileAnalyser(_ast, RootContext(_ast)).analyse()

        list_builtin = Builtin("list", has_affect=False)
        expected = {
            Func("a_func", ["arg"], None, None): {
                "gets": set(),
                "sets": {
                    Name("d"),
                },
                "dels": set(),
                "calls": {Call("list()", [], {}, target=list_builtin)},
            }
        }

        assert results == expected
