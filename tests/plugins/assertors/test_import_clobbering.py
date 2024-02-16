from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

import tests.helpers as helpers
from rattr.models.context import Context
from rattr.plugins.assertors.import_clobbering import ImportClobberingAssertor

if TYPE_CHECKING:
    import ast
    from typing import Callable


class TestImportNameClobbering:
    def test_would_be_clobbered_but_is_renamed(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi as pie

            pi = 3.2 - 0.06 + 0.001 # ...
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert not _exit.called

    def test_clobber_at_module_level(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            import math

            math = "this is very bad"
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'math'")],
        )

        assert _exit.called

    def test_clobber_in_child_context(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from os.path import join

            def func():
                join = "this" + "joined with" + "this"
                return join
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'join'")],
        )

        assert _exit.called

    def test_clobber_in_multiple_assignment(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from os.path import join

            def func():
                a, b, join, d = 1, 2, 3, 4
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'join'")],
        )

        assert _exit.called

    def test_clobber_in_annotated_assignment(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            import math

            math: str = "this is very bad"
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'math'")],
        )

        assert _exit.called

    def test_clobber_in_augmented_assignment(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            pi += 1.0   # that's not pi!
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'pi'")],
        )

        assert _exit.called

    def test_clobber_by_function_definition(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from os.path import join

            def join(*args):
                return "/".join(args)
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'join'")],
        )

        assert _exit.called

    def test_clobber_by_nested_function_definition(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from os.path import join

            def wrapper():
                def join(*args):
                    return "/".join(args)
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'join'")],
        )

        assert _exit.called

    def test_clobber_by_async_function_definition(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from os.path import join

            async def join(*args):
                return "/".join(args)
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'join'")],
        )

        assert _exit.called

    def test_clobber_by_class_definition(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from pathlib import Path

            class Path:
                ...
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'Path'")],
        )

        assert _exit.called

    def test_clobber_by_argument_name(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            def area(r, pi):
                return pi * r * r
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'pi'")],
        )

        assert _exit.called

    def test_clobber_by_argument_name_in_nested_function(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            def wrapped():
                def area(r, pi):
                    return pi * r * r
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'pi'")],
        )

        assert _exit.called

    def test_clobber_by_argument_name_in_async_function(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            async def area(r, pi):
                return pi * r * r
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'pi'")],
        )

        assert _exit.called

    def test_clobber_by_argument_name_in_lambda(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            x = lambda pi: 3.14
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'pi'")],
        )

        assert _exit.called

    def test_clobber_by_iterator_name_in_for_loop(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            for pi in pies:
                eat(pi)  # yum
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'pi'")],
        )

        assert _exit.called

    def test_clobber_by_iterator_name_in_for_loop_while_unpacking(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            for a, pi in pies:
                eat(pi)
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'pi'")],
        )

        assert _exit.called

    def test_clobber_by_iterator_name_in_async_for_loop(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            async for pi in pies:
                eat(pi)  # yum
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'pi'")],
        )

        assert _exit.called

    def test_clobber_by_name_in_with_statement(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            def fn():
                with whatever as pi:
                    pass
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'pi'")],
        )

        assert _exit.called

    def test_clobber_by_name_in_with_statement_while_unpacking(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            def fn():
                with whatever as we, whenever as pi:
                    pass
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'pi'")],
        )

        assert _exit.called

    def test_clobber_by_name_in_async_with_statement(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            def fn():
                async with whatever as pi:
                    pass
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'pi'")],
        )

        assert _exit.called

    def test_clobber_by_iterator_name_in_list_comprehension(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            l = [pi for pi in pies]
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'pi'")],
        )

        assert _exit.called

    def test_clobber_by_iterator_name_in_set_comprehension(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            s = {pi for _, pi in pastries_and_pies}
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'pi'")],
        )

        assert _exit.called

    def test_clobber_by_iterator_name_in_dict_comprehension(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            r"""
            from math import pi

            d = {pi: filling for pi, filling in pies}
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'pi'")],
        )

        assert _exit.called

    def test_clobber_by_iterator_name_in_generator_expression(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            is_any = any(pi for pi in pies)
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'pi'")],
        )

        assert _exit.called


class TestDoNotFailOnPotentialFalsePositives:
    def test_allow_attribute_write(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
    ):
        _ast, _ctx = parse_with_context(
            """
            from pathlib import Path
            from math import pi

            Path.attr = "on class"
            MyClass.pi = "on attr"
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert not _exit.called

    def test_allow_attribute_write_in_chained_assignment(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
    ):
        _ast, _ctx = parse_with_context(
            """
            from pathlib import Path
            from math import pi

            thing = Path.attr = "on class"
            thing = MyClass.pi = "on attr"
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert not _exit.called


class TestMultipleClobbersWithLocation:
    def test_multiple_failures_with_location(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            def fn():
                del pi

                def inner():
                    pi = 1

                del pi, again
                pi = 2
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [
                helpers.as_fatal("attempt to delete imported name 'pi'", line=4, col=4),
                helpers.as_fatal("redefinition of imported name 'pi'", line=7, col=8),
                helpers.as_fatal("attempt to delete imported name 'pi'", line=9, col=4),
                helpers.as_fatal("redefinition of imported name 'pi'", line=10, col=4),
            ],
        )

        assert _exit.called


class TestIgnoreAnnotatedClobbers:
    def test_ignore_clobbers_with_rattr_ignore(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import func, async_func, SomeClass

            @rattr_ignore()
            def func():
                pass

            @rattr_ignore()
            async def async_func():
                pass

            @rattr_ignore()
            class SomeClass:
                pass
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert not _exit.called

    def test_ignore_clobbers_with_rattr_results(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import func, async_func, SomeClass

            @rattr_results()
            def func():
                pass

            @rattr_results()
            async def async_func():
                pass

            @rattr_results()
            class SomeClass:
                pass
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert not _exit.called


class TestDeleteImportedName:
    def test_delete_imported_name(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            def fn():
                del pi
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("attempt to delete imported name 'pi'")],
        )

        assert _exit.called

    def test_delete_imported_name_in_multiple_delete(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            def fn():
                del a, b, pi
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("attempt to delete imported name 'pi'")],
        )

        assert _exit.called


class TestNameClobberedByMethod:
    def test_simple_failure(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
        capfd: pytest.CaptureFixture[str],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            pizza = 5  # good
            pi = 1  # bad, the name `bar` is clobbered
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert helpers.stderr_matches(
            capfd,
            [helpers.as_fatal("redefinition of imported name 'pi'")],
        )

        assert _exit.called

    def test_do_not_fail_on_method_name(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            class MyClass:
                def pi(self):
                    ...
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert not _exit.called

    def test_do_not_fail_on_property_name(
        self,
        parse_with_context: Callable[[str], tuple[ast.AST, Context]],
    ):
        _ast, _ctx = parse_with_context(
            """
            from math import pi

            class MyClass:
                @property
                def pi(self):
                    ...
            """
        )

        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(_ast, _ctx)

        assert not _exit.called
