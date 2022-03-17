from unittest import mock

from rattr.analyser.context import RootContext
from rattr.plugins.assertors.import_clobbering import ImportClobberingAssertor


class TestImportClobberingAssertor:
    def test_allow_non_clobbering(self, parse):
        _ast = parse(
            """
            from math import pi as pie

            pi = 3.2 - 0.06 + 0.001 # ...
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        assert not _exit.called

    def test_assign_to_imported_name(self, parse, capfd):
        # In root context
        _ast = parse(
            """
            import math

            math = "this is very bad"
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

        # In child context
        _ast = parse(
            """
            from os.path import join

            def func():
                join = "this" + "joined with" + "this"
                return join
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

        # Tuple assignment
        _ast = parse(
            """
            from os.path import join

            def func():
                a, b, join, d = 1, 2, 3, 4
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

    def test_annassign_to_imported_name(self, parse, capfd):
        _ast = parse(
            """
            import math

            math: str = "this is very bad"
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

    def test_augassign_to_imported_name(self, parse, capfd):
        _ast = parse(
            """
            from math import pi

            pi += 1.0   # that's not pi!
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

    def test_delete_of_imported_name(self, parse, capfd):
        # Single
        _ast = parse(
            """
            from math import pi

            def fn():
                del pi
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "attempt to delete imported name" in output
        assert _exit.called

        # Tuple
        _ast = parse(
            """
            from math import pi

            def fn():
                del a, b, pi
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "attempt to delete imported name" in output
        assert _exit.called

    def test_function_def(self, parse, capfd):
        # Root
        _ast = parse(
            """
            from os.path import join

            def join(*args):
                return "/".join(args)
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

        # Nested
        _ast = parse(
            """
            from os.path import join

            def wrapper():
                def join(*args):
                    return "/".join(args)
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

    def test_async_function_def(self, parse, capfd):
        # Root
        _ast = parse(
            """
            from os.path import join

            async def join(*args):
                return "/".join(args)
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

    def test_class_def(self, parse, capfd):
        _ast = parse(
            """
            from module.submodule import SomeClass

            class SomeClass:
                pass
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

    def test_respect_rattr_ignore(self, parse):
        _ast = parse(
            """
            from math import func, async_func, SomeClass

            @rattr_ignore
            def func():
                pass

            @rattr_ignore
            async def async_func():
                pass

            @rattr_ignore
            class SomeClass:
                pass
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        assert not _exit.called

    def test_respect_rattr_results(self, parse):
        _ast = parse(
            """
            from math import func, async_func, SomeClass

            @rattr_results
            def func():
                pass

            @rattr_results
            async def async_func():
                pass

            @rattr_results
            class SomeClass:
                pass
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        assert not _exit.called

    def test_argument_name(self, parse, capfd):
        # Normal
        _ast = parse(
            """
            from math import pi

            def area(r, pi):
                return pi * r * r
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

        # Nested
        _ast = parse(
            """
            from math import pi

            def wrapped():
                def area(r, pi):
                    return pi * r * r
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

        # Async
        _ast = parse(
            """
            from math import pi

            async def area(r, pi):
                return pi * r * r
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

    def test_lambda(self, parse, capfd):
        _ast = parse(
            """
            from math import pi

            x = lambda pi: 3.14
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

    def test_for(self, parse, capfd):
        # For
        _ast = parse(
            """
            from math import pi

            for pi in pies:
                eat(pi)
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

        # Tuple
        _ast = parse(
            """
            from math import pi

            for a, pi in pies:
                eat(pi)
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

        # Async
        _ast = parse(
            """
            from math import pi

            async for pi in pies:
                eat(pi)
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

    def test_with(self, parse, capfd):
        # With
        _ast = parse(
            """
            from math import pi

            with whatever as pi:
                pass
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

        # Multi
        _ast = parse(
            """
            from math import pi

            with whatever as we, whenever as pi:
                pass
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

        # Async
        _ast = parse(
            """
            from math import pi

            async with whatever as pi:
                pass
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

    def test_comprehension(self, parse, capfd):
        # List
        _ast = parse(
            """
            from math import pi

            l = [pi for pi in pies]
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

        # Set
        _ast = parse(
            """
            from math import pi

            s = {pi for _, pi in pastries_and_pies}
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

        # Generator expression
        _ast = parse(
            """
            from math import pi

            is_any = any(pi for pi in pies)
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called

        # Dict
        _ast = parse(
            """
            from math import pi

            d = {pi: filling for pi, filling in pies}
        """
        )
        with mock.patch("sys.exit") as _exit:
            ImportClobberingAssertor(is_strict=True).assert_holds(
                _ast, RootContext(_ast)
            )

        output, _ = capfd.readouterr()

        assert "redefinition of imported name" in output
        assert _exit.called
