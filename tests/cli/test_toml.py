from __future__ import annotations

import argparse
from pathlib import Path
from unittest import mock

import pytest

from rattr.cli.parser import _parse_project_config, parse_arguments
from rattr.config import Arguments, Output
from rattr.versioning import is_python_version


class TestToml:
    def test_illegal_field_is_filtered(
        self, required_sys_args, toml_with_illegal_field, illegal_field_name
    ):
        arguments = parse_arguments(
            sys_args=required_sys_args,
            project_toml_conf=toml_with_illegal_field,
            exit_on_error=False,
        )
        assert hasattr(arguments, illegal_field_name) is False

    def test_valid_toml(self, required_sys_args, toml_well_formed):
        arguments = parse_arguments(
            sys_args=required_sys_args,
            project_toml_conf=toml_well_formed,
            exit_on_error=False,
        )
        assert arguments == Arguments(
            # From toml
            _follow_imports_level=3,
            _excluded_imports=["a\\.b\\.c", "a\\.b.*", "a\\.b\\.c\\.e", "a\\.b\\.c.*"],
            _excluded_names=["a_.*", "b_.*", "_.*"],
            _warning_level="all",
            threshold=1,
            # From sys_args
            target=Path("my/rattr/target.py"),
            # Defaults
            pyproject_toml_override=None,
            collapse_home=False,
            truncate_deep_paths=False,
            is_strict=False,
            stdout=Output.results,
            force_refresh_cache=False,
            cache_file=None,
        )

    def test_valid_toml_without_sys_args(self, toml_well_formed):
        with pytest.raises(
            argparse.ArgumentError,
            match="the following arguments are required: <file>",
        ):
            parse_arguments(
                sys_args=[],
                project_toml_conf=toml_well_formed,
                exit_on_error=False,
            )

    def test_toml_is_overwritten_by_sys_args(self, required_sys_args):
        sys_args = [
            "--follow-imports",
            "3",
            "--threshold",
            "8",
            "--exclude",
            "fn_excluded_1",
            "--exclude",
            "fn_excluded_2",
            "--exclude",
            "fn_excluded_3",
            "this/is/the/target.py",
        ]
        toml = {"threshold": 500, "exclude": ["fn_excluded_4", "fn_excluded_5"]}

        # Sys only
        arguments = parse_arguments(
            sys_args=sys_args,
            project_toml_conf={},
            exit_on_error=False,
        )
        assert arguments == Arguments(
            # Defaults
            pyproject_toml_override=None,
            _warning_level="default",
            _excluded_imports=None,
            is_strict=False,
            threshold=8,
            collapse_home=False,
            truncate_deep_paths=False,
            stdout=Output.results,
            force_refresh_cache=False,
            cache_file=None,
            # Sys args
            _follow_imports_level=3,
            _excluded_names=["fn_excluded_1", "fn_excluded_2", "fn_excluded_3"],
            target=Path("this/is/the/target.py"),
        )

        # Toml only
        arguments = parse_arguments(
            sys_args=required_sys_args,
            project_toml_conf=toml,
            exit_on_error=False,
        )
        assert arguments == Arguments(
            # Defaults
            pyproject_toml_override=None,
            _follow_imports_level=1,
            _warning_level="default",
            _excluded_imports=None,
            collapse_home=False,
            truncate_deep_paths=False,
            is_strict=False,
            stdout=Output.results,
            force_refresh_cache=False,
            cache_file=None,
            # Toml
            _excluded_names=["fn_excluded_4", "fn_excluded_5"],
            threshold=500,
            # Required sys arg
            target=Path("my/rattr/target.py"),
        )

        # Both
        arguments = parse_arguments(
            sys_args=sys_args,
            project_toml_conf=toml,
            exit_on_error=False,
        )
        assert arguments == Arguments(
            # Defaults
            pyproject_toml_override=None,
            _follow_imports_level=3,
            _warning_level="default",
            _excluded_imports=None,
            collapse_home=False,
            truncate_deep_paths=False,
            is_strict=False,
            stdout=Output.results,
            force_refresh_cache=False,
            cache_file=None,
            # From toml and sys args
            _excluded_names=[
                "fn_excluded_4",
                "fn_excluded_5",
                "fn_excluded_1",
                "fn_excluded_2",
                "fn_excluded_3",
            ],
            # From sys args
            threshold=8,  # 500 from toml, overwritten by sys args
            target=Path("this/is/the/target.py"),
        )


class TestTomlValidation:
    @pytest.mark.parametrize(
        ("toml,expected_type,actual_type"),
        [
            ({"follow-imports": "1"}, "int", "str"),
            ({"follow-imports": ["1"]}, "int", "list[str]"),
            ({"exclude-imports": "1"}, "list[str]", "str"),
            ({"exclude-imports": [1, 2]}, "list[str]", "list[int]"),
            ({"exclude": "1"}, "list[str]", "str"),
            ({"exclude": [1, "2"]}, "list[str]", "list[int | str]"),
            ({"warning-level": 1}, "str", "int"),
            ({"warning-level": True}, "str", "bool"),
            ({"collapse-home": "1"}, "bool", "str"),
            ({"collapse-home": 1}, "bool", "int"),
            ({"truncate-deep-paths": ["1", "two"]}, "bool", "list[str]"),
            ({"truncate-deep-paths": [1, 2, None]}, "bool", "list[NoneType | int]"),
            ({"strict": "True"}, "bool", "str"),
            ({"strict": None}, "bool", "NoneType"),
            ({"threshold": 1.0}, "int", "float"),
            ({"threshold": None}, "int", "NoneType"),
            ({"stdout": 1.0}, "str", "float"),
            ({"stdout": None}, "str", "NoneType"),
        ],
    )
    def test_toml_type_error(self, required_sys_args, toml, expected_type, actual_type):
        for _field, _value in toml.items():
            field, value = _field, _value

        with pytest.raises(argparse.ArgumentError) as argument_error:
            parse_arguments(
                sys_args=required_sys_args,
                project_toml_conf=toml,
                exit_on_error=False,
            )

        _type_error = (
            "{arg!r} expects type {expected_type}, got {value!r} of type {actual_type}"
        )
        assert argument_error.value.message == _type_error.format(
            arg=field,
            expected_type=expected_type,
            value=value,
            actual_type=actual_type,
        )

    @pytest.mark.parametrize(
        ("toml,error"),
        [
            (
                {"follow-imports": 100},
                (
                    "invalid choice: 100 (choose from 0, 1, 2, 3)"
                    if is_python_version("<=3.11")
                    else "invalid choice: '100' (choose from 0, 1, 2, 3)"
                ),
            ),
            (
                {"warning-level": "this-is-nonsense-but-well-typed"},
                (
                    "invalid choice: 'this-is-nonsense-but-well-typed' (choose from 'none', 'local', 'default', 'all')"
                    if is_python_version("<=3.11")
                    else "invalid choice: 'this-is-nonsense-but-well-typed' (choose from none, local, default, all)"
                ),
            ),
            (
                {"stdout": "this-is-nonsense-but-well-typed"},
                "invalid Output value: 'this-is-nonsense-but-well-typed'",
            ),
        ],
    )
    def test_toml_type_is_correct_and_value_is_invalid(
        self, required_sys_args, toml, error
    ):
        with pytest.raises(argparse.ArgumentError) as argument_error:
            parse_arguments(
                sys_args=required_sys_args,
                project_toml_conf=toml,
                exit_on_error=False,
            )

        assert argument_error.value.message == error

    @pytest.mark.parametrize(
        ("toml"),
        [
            ({"follow-imports": 0}),
            ({"follow-imports": 3}),
            ({"exclude-imports": ["time"]}),
            ({"exclude-imports": ["time", "os"]}),
            ({"exclude": ["my_func"]}),
            ({"exclude": ["your_func", "our_func"]}),
            ({"warning-level": "all"}),
            ({"warning-level": "default"}),
            ({"collapse-home": True}),
            ({"collapse-home": False}),
            ({"truncate-deep-paths": True}),
            ({"truncate-deep-paths": False}),
            ({"strict": True}),
            ({"strict": False}),
            ({"threshold": 1}),
            ({"threshold": -600}),  # Invalid but checked by `validate_arguments`
            ({"stdout": "ir"}),
            ({"stdout": "results"}),
        ],
    )
    def test_toml_type_is_correct_and_value_is_valid(self, required_sys_args, toml):
        arguments = parse_arguments(
            sys_args=required_sys_args,
            project_toml_conf=toml,
            exit_on_error=False,
        )
        assert str(arguments.target.as_posix()) == "my/rattr/target.py"


class TestTomlOverride:
    @mock.patch("rattr.cli.parser._toml_error")
    @mock.patch("rattr.cli.parser.parse_project_toml")
    def test_parse_project_config_from_input_config(
        self,
        m_parse_project_toml,
        m_toml_error,
        illegal_field_name,
        toml_override_path,
        toml_override,
    ):
        # Test 1 -- input config given, should just be validated and returned
        input_config = {
            "threshold": 1,
            "strict": True,
            illegal_field_name: "skip-me",
        }

        input_config_valid_only = input_config.copy()
        _ = input_config_valid_only.pop(illegal_field_name)

        assert (
            _parse_project_config(input_config=input_config, project_toml_override=None)
            == input_config_valid_only
        )
        assert (
            _parse_project_config(
                input_config=input_config, project_toml_override=toml_override_path
            )
            == input_config_valid_only
            != toml_override
        )

        assert not m_toml_error.called
        assert not m_parse_project_toml.called

    @mock.patch("rattr.cli.parser._toml_error")
    @mock.patch("rattr.cli.parser.find_pyproject_toml")
    def test_parse_project_config_from_pyproject_toml(
        self,
        m_find_pyproject_toml,
        m_toml_error,
        toml_well_formed_path,
        toml_well_formed,
    ):
        m_pyproject_toml = mock.Mock(spec=Path)
        m_pyproject_toml.is_file.return_value = True
        m_pyproject_toml.read_text.return_value = toml_well_formed_path.read_text()

        m_find_pyproject_toml.return_value = m_pyproject_toml

        assert (
            _parse_project_config(input_config={}, project_toml_override=None)
            == toml_well_formed
        )
        assert not m_toml_error.called

    @mock.patch("rattr.cli.parser._toml_error")
    @mock.patch("rattr.cli.parser.find_pyproject_toml")
    def test_parse_project_config_from_override(
        self,
        m_find_pyproject_toml,
        m_toml_error,
        toml_well_formed_path,
        toml_well_formed,
        toml_override_path,
        toml_override,
    ):
        m_pyproject_toml = mock.Mock(spec=Path)
        m_pyproject_toml.is_file.return_value = True
        m_pyproject_toml.read_text.return_value = toml_well_formed_path.read_text()

        m_find_pyproject_toml.return_value = m_pyproject_toml

        assert (
            _parse_project_config(
                input_config={}, project_toml_override=toml_override_path
            )
            == toml_override
            != toml_well_formed
        )
        assert not m_toml_error.called
