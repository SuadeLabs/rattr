from __future__ import annotations

from unittest import mock

import pytest

from rattr.versioning._util import _parse_version_string, is_python_version


class TestParseVersionString:
    def test_parse_version_string_empty_string(self):
        with pytest.raises(ValueError):
            _parse_version_string("")

    def test_parse_version_string_no_opcode(self):
        assert _parse_version_string("3.123") == ("==", "3.123")
        assert _parse_version_string("3.12.3") == ("==", "3.12.3")

    def test_parse_version_string_no_opcode_malformed(self):
        # must have major and minor
        with pytest.raises(ValueError):
            _parse_version_string("3")

        # too many components
        with pytest.raises(ValueError):
            _parse_version_string("3.1.2.4")

        # must be 3.x
        with pytest.raises(ValueError):
            _parse_version_string("1.2.3")

        # not "." separated
        with pytest.raises(ValueError):
            _parse_version_string("1,2")

        # parts not well formed (trailing ".")
        with pytest.raises(ValueError):
            _parse_version_string("1.2.")

    def test_parse_version_string_no_version(self):
        with pytest.raises(ValueError):
            _parse_version_string(">=")

        with pytest.raises(ValueError):
            _parse_version_string(">=abcd")

    def test_parse_version_string(self):
        assert (
            _parse_version_string(">=3.1")
            == _parse_version_string(" > =   3 . 1 ")
            == (">=", "3.1")
        )

        assert (
            _parse_version_string(">=3.123.456")
            == _parse_version_string(" > =   3.123.456 ")
            == _parse_version_string(" > =   3.   12  3.456 ")
            == (">=", "3.123.456")
        )


class TestIsPythonVersion:
    @mock.patch("rattr.versioning._util._current_version", lambda: (3, 7, 1))
    def test_is_python_version_bounds(self):
        assert is_python_version(">=3.7")
        assert is_python_version("==3.7")
        assert is_python_version("<=3.7")
        assert not is_python_version(">3.7") and is_python_version(">3.7.0")
        assert not is_python_version("<3.7") and not is_python_version("<3.7.0")

        assert is_python_version(">=3.7.1")
        assert is_python_version("==3.7.1")
        assert is_python_version("<=3.7.1")
        assert not is_python_version(">3.7.1")
        assert not is_python_version("<3.7.1")

    @mock.patch("rattr.versioning._util._current_version", lambda: (3, 9, 1))
    def test_10_vs_9(self):
        # Originally this used string comparison and thus failed as for strings
        # 3.9 > 3.10, now this uses float comparison sans the major version number.
        assert is_python_version(">=3.9")
        assert not is_python_version(">3.9")
        assert is_python_version("==3.9")
        assert not is_python_version("<3.9")
        assert is_python_version("<=3.9")

        assert not is_python_version(">=3.10")
        assert not is_python_version(">3.10")
        assert not is_python_version("==3.10")
        assert is_python_version("<3.10")
        assert is_python_version("<=3.10")

    @mock.patch("rattr.versioning._util._current_version", lambda: (3, 9, 1))
    def test_10_vs_9_with_micro(self):
        # Originally this used string comparison and thus failed as for strings
        # 3.9 > 3.10, now this uses float comparison sans the major version number.
        assert is_python_version(">=3.9.1")
        assert not is_python_version(">3.9.1")
        assert is_python_version("==3.9.1")
        assert not is_python_version("<3.9.1")
        assert is_python_version("<=3.9.1")

        assert not is_python_version(">=3.10.1")
        assert not is_python_version(">3.10.1")
        assert not is_python_version("==3.10.1")
        assert is_python_version("<3.10.1")
        assert is_python_version("<=3.10.1")
