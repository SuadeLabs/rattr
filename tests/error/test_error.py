from __future__ import annotations

from functools import partial
from pathlib import Path
from unittest import mock

import pytest

from rattr import error


class TestError:
    def test_rattr(self, capfd):
        _message = "the error message"

        with mock.patch("sys.exit") as _exit:
            error.rattr(_message)

        _, stderr = capfd.readouterr()

        assert "rattr" in stderr
        assert _message in stderr
        assert not _exit.called

    def test_info(self, capfd, arguments):
        _message = "the error message"

        with arguments(_warning_level="all"):
            with mock.patch("sys.exit") as _exit:
                error.info(_message)

        _, stderr = capfd.readouterr()

        assert "info" in stderr
        assert _message in stderr
        assert not _exit.called

    def test_warning(self, capfd):
        _message = "the error message"

        with mock.patch("sys.exit") as _exit:
            error.warning(_message)

        _, stderr = capfd.readouterr()

        assert "warning" in stderr
        assert _message in stderr
        assert not _exit.called

    def test_error(self, capfd):
        _message = "the error message"

        with mock.patch("sys.exit") as _exit:
            error.error(_message)

        _, stderr = capfd.readouterr()

        assert "error" in stderr
        assert _message in stderr
        assert not _exit.called

    def test_fatal(self, capfd):
        _message = "the error message"

        with mock.patch("sys.exit") as _exit:
            error.fatal(_message)

        _, stderr = capfd.readouterr()

        assert "fatal" in stderr
        assert _message in stderr
        assert _exit.called and _exit.call_count == 1


class TestErrorBadness:
    @pytest.fixture
    def reset(self, state):
        return partial(
            state,
            badness_from_simplification=0,
            badness_from_target_file=0,
            badness_from_imports=0,
            current_file=Path("target.py"),
        )

    def test_rattr(self, config, reset):
        # `error.rattr` takes badness to have a consistent interface, but does not
        # affect badness
        with reset():
            assert config.state.badness == 0
            error.rattr("blah", badness=1)
            assert config.state.badness == 0

    def test_info(self, config, reset):
        with reset():
            assert config.state.badness == 0
            error.info("blah", badness=1)
            assert config.state.badness == 1

    def test_warning(self, config, reset):
        with reset():
            assert config.state.badness == 0
            error.warning("blah", badness=1)
            assert config.state.badness == 1

    def test_error(self, config, reset):
        with reset():
            assert config.state.badness == 0
            error.error("blah", badness=1)
            assert config.state.badness == 1

    def test_fatal(self, config, reset):
        with reset():
            assert config.state.badness == 0
            with pytest.raises(SystemExit):
                error.fatal("blah", badness=1)
            assert config.state.badness == 1
