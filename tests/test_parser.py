from argparse import ArgumentError, Namespace

import pytest

from rattr.cli.parser import parse_arguments


class TestParser:
    def test_toml_dict_with_illegal_fields(
        self, toml_dict_with_illegal_fields, illegal_field_name, sys_args1
    ):
        args = parse_arguments(
            sys_args=sys_args1,
            project_toml_cfg=toml_dict_with_illegal_fields,
            exit_on_error=False,
        )
        # illegal field should be left out from parsed args
        assert hasattr(args, illegal_field_name) is False

    def test_toml_dict_with_bad_field_types(
        self, toml_dicts_with_bad_field_types_and_errors
    ):
        for toml_dict, error_message in toml_dicts_with_bad_field_types_and_errors:
            with pytest.raises(ArgumentError) as exc_info:
                parse_arguments(project_toml_cfg=toml_dict, exit_on_error=False)
            assert str(exc_info.value) == error_message

    def test_toml_dicts_with_mutex_arg_violation(
        self, toml_dicts_with_mutex_arg_violation_and_errors
    ):
        for toml_dict, error_message in toml_dicts_with_mutex_arg_violation_and_errors:
            with pytest.raises(ArgumentError) as exc_info:
                parse_arguments(project_toml_cfg=toml_dict, exit_on_error=False)
            assert str(exc_info.value) == error_message

    def test_toml_dict_without_file_from_cli_call(self, correct_toml_dict1):
        with pytest.raises(ArgumentError) as exc_info:
            parse_arguments(
                # empty 'sys_args' imply no file specified in cli call
                sys_args=[],
                project_toml_cfg=correct_toml_dict1,
                exit_on_error=False,
            )

        error_message = "rattr: error: the following arguments are required: <file>\n"
        assert str(exc_info.value) == error_message

    def test_strict_toml_dict_with_file_from_cli_call(
        self, sys_args1, correct_toml_dict1
    ):
        args = parse_arguments(
            sys_args=sys_args1[1:],
            project_toml_cfg=correct_toml_dict1,
            exit_on_error=False,
        )

        exp_args = Namespace(
            follow_imports=3,
            exclude_import=["a\\.a\\.a", "b\\.b.*", "c\\.c\\.c\\.c", "d\\d\\.d.*"],
            exclude=["a_.*", "b_.*", "c_.*"],
            show_warnings="all",
            show_path="short",
            strict=True,
            permissive=False,
            show_ir=False,
            show_results=True,
            show_stats=False,
            silent=False,
            cache="cache.json",
            threshold=0,
            filter_string="",
            file="rattr/cli/parser.py",
        )

        assert args == exp_args

    def test_permissive_toml_dict_with_file_from_cli_call(
        self, sys_args1, correct_toml_dict2
    ):
        args = parse_arguments(
            sys_args=sys_args1[1:],
            project_toml_cfg=correct_toml_dict2,
            exit_on_error=False,
        )

        exp_args = Namespace(
            follow_imports=3,
            exclude_import=["a\\.a\\.a", "b\\.b.*", "c\\.c\\.c\\.c", "d\\d\\.d.*"],
            exclude=["a_.*", "b_.*", "c_.*"],
            show_warnings="all",
            show_path="full",
            strict=False,
            permissive=True,
            show_ir=False,
            show_results=True,
            show_stats=False,
            silent=False,
            cache="cache.json",
            threshold=1,
            filter_string="",
            file="rattr/cli/parser.py",
        )

        assert args == exp_args

    def test_toml_dict_with_overwrites_from_cli_call(
        self, sys_args2, correct_toml_dict1
    ):
        args = parse_arguments(
            sys_args=sys_args2[1:],
            project_toml_cfg=correct_toml_dict1,
            exit_on_error=False,
        )

        exp_args = Namespace(
            follow_imports=2,
            exclude_import=["a\\.a\\.a", "b\\.b.*", "c\\.c\\.c\\.c", "d\\d\\.d.*"],
            exclude=["a_.*", "b_.*", "c_.*"],
            show_warnings="file",
            show_path="short",
            strict=True,
            permissive=False,
            show_ir=False,
            show_results=True,
            show_stats=False,
            silent=False,
            cache="cache.json",
            threshold=0,
            filter_string="",
            file="rattr/cli/argparse.py",
        )

        assert args == exp_args

    def test_toml_dict_with_append_and_overwrites_from_cli_call(
        self, sys_args3, correct_toml_dict1
    ):
        args = parse_arguments(
            sys_args=sys_args3[1:],
            project_toml_cfg=correct_toml_dict1,
            exit_on_error=False,
        )

        exp_args = Namespace(
            follow_imports=2,
            exclude_import=[
                "a\\.a\\.a",
                "b\\.b.*",
                "c\\.c\\.c\\.c",
                "d\\d\\.d.*",
                "*exclude-import*",
            ],
            exclude=["a_.*", "b_.*", "c_.*", "*exclude-pattern*"],
            show_warnings="file",
            show_path="short",
            strict=True,
            permissive=False,
            show_ir=False,
            show_results=False,
            show_stats=False,
            silent=True,
            cache="cache.json",
            threshold=0,
            filter_string="",
            file="rattr/cli/argparse.py",
        )

        assert args == exp_args

    def test_toml_dict_with_overwrites_and_mutex_arg_switch(
        self, sys_args2, correct_toml_dict2
    ):
        args = parse_arguments(
            sys_args=sys_args2[1:],
            project_toml_cfg=correct_toml_dict2,
            exit_on_error=False,
        )

        exp_args = Namespace(
            follow_imports=2,
            exclude_import=["a\\.a\\.a", "b\\.b.*", "c\\.c\\.c\\.c", "d\\d\\.d.*"],
            exclude=["a_.*", "b_.*", "c_.*"],
            show_warnings="file",
            show_path="short",
            strict=True,
            permissive=False,
            show_ir=False,
            show_results=True,
            show_stats=False,
            silent=False,
            cache="cache.json",
            threshold=0,
            filter_string="",
            file="rattr/cli/argparse.py",
        )

        assert args == exp_args

    def test_toml_dict_with_mutex_violation_cli_overwrite(
        self, sys_args4, correct_toml_dict3
    ):

        with pytest.raises(ArgumentError) as exc_info:
            parse_arguments(
                sys_args=sys_args4[1:],
                project_toml_cfg=correct_toml_dict3,
                exit_on_error=False,
            )

        error_message = "-irs ('--show-ir', '--show-results', '--show-stats') and -S ('--silent') are mutually exclusive"  # noqa: E501
        assert str(exc_info.value) == error_message

    def test_empty_toml_dict_with_only_cli_call(self, sys_args4):
        args = parse_arguments(
            # empty 'sys_args' imply no file specified in cli call
            sys_args=sys_args4[1:],
            project_toml_cfg={},
            exit_on_error=False,
        )

        exp_args = Namespace(
            follow_imports=1,
            exclude_import=[],
            exclude=[],
            show_warnings="all",
            show_path="short",
            strict=False,
            permissive=True,
            show_ir=False,
            show_results=False,
            show_stats=False,
            silent=True,
            cache="",
            filter_string="",
            file="rattr/cli/parser.py",
            threshold=0,
        )

        assert args == exp_args

    def test_permissive_cli_call_overwrite(self, sys_args5, correct_toml_dict2):
        args = parse_arguments(
            sys_args=sys_args5[1:],
            project_toml_cfg=correct_toml_dict2,
            exit_on_error=False,
        )

        exp_args = Namespace(
            follow_imports=3,
            exclude_import=["a\\.a\\.a", "b\\.b.*", "c\\.c\\.c\\.c", "d\\d\\.d.*"],
            exclude=["a_.*", "b_.*", "c_.*"],
            show_warnings="all",
            show_path="full",
            strict=False,
            permissive=True,
            show_ir=False,
            show_results=True,
            show_stats=False,
            silent=False,
            cache="cache.json",
            threshold=3,
            filter_string="",
            file="rattr/cli/parser.py",
        )

        assert args == exp_args
