from __future__ import annotations

from unittest import mock

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
