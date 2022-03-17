# """Full "end-to-end" Rattr tests."""

# import pytest

# from rattr.__main__ import main, validate_arguments


# class TestRattr:

#     def test_validate_arguments(self, snippet, capfd):
#         # Non-existent file
#         with pytest.raises(FileNotFoundError):
#             validate_arguments({
#                 "<file>": snippet("no_such_file.py")
#             })

#         # Non-Python file
#         validate_arguments({"<file>": snippet("not_a_py.file")})
#         output, _ = capfd.readouterr()
#         assert "expects '.py'" in output

#         # Default filter string
#         filter_string = validate_arguments({
#             "<file>": snippet("rattr_full_one.py")
#         }).get("filter_string")
#         assert filter_string == ".+"

#     def test_rattr_full_one(self, snippet, capfd):
#         main({
#             "follow_imports": False,
#             "verbose": False,
#             "print_ast": False,
#             "debug": False,
#             "file": snippet("rattr_full_one.py"),
#             "filter_string": ".*",
#         })

#         output, _ = capfd.readouterr()

#         expected = """{
#     "a_normal_function": {
#         "sets": [],
#         "gets": [
#             "arg_one.attr"
#         ],
#         "dels": [],
#         "calls": [
#             "ValueError()"
#         ]
#     },
#     "update_attribute": {
#         "sets": [
#             "obj.target"
#         ],
#         "gets": [
#             "obj.name",
#             "new_value"
#         ],
#         "dels": [],
#         "calls": [
#             "config.get()",
#             "print()"
#         ]
#     },
#     "area": {
#         "sets": [],
#         "gets": [
#             "pi",
#             "circle.radius"
#         ],
#         "dels": [],
#         "calls": []
#     },
#     "is_a_foorbar": {
#         "sets": [
#             "filepath"
#         ],
#         "gets": [
#             "datatype.target_file",
#             "filepath",
#             "datatype.is_foo",
#             "datatype.is_bar"
#         ],
#         "dels": [],
#         "calls": [
#             "path.isfile()"
#         ]
#     },
#     "make_an_assignment": {
#         "sets": [
#             "assignee.attr"
#         ],
#         "gets": [
#             "value"
#         ],
#         "dels": [],
#         "calls": []
#     }
# }"""

#         assert "ArgumentAssignmentAssertor: line 38:" in output
#         assert expected in output

#     def test_rattr_results_one(self, snippet, capfd):
#         main({
#             "follow_imports": False,
#             "verbose": False,
#             "print_ast": False,
#             "debug": False,
#             "file": snippet("rattr_results_one.py"),
#             "filter_string": ".*",
#         })

#         output, _ = capfd.readouterr()

#         expected = """{
#     "fn_a": {
#         "sets": [
#             "a.attr"
#         ],
#         "gets": [
#             "b.attr"
#         ],
#         "dels": [],
#         "calls": []
#     },
#     "fn_b": {
#         "sets": [
#             "c.attr"
#         ],
#         "gets": [
#             "c.attr"
#         ],
#         "dels": [],
#         "calls": [
#             "fn_a()"
#         ]
#     }
# }
# """

#         assert "ExpectedDecoratorAssertor: line 2:" in output
#         assert expected in output

#     def test_rattr_results_two(self, snippet, capfd):
#         main({
#             "follow_imports": False,
#             "verbose": False,
#             "print_ast": False,
#             "debug": False,
#             "file": snippet("rattr_results_two.py"),
#             "filter_string": ".*",
#         })

#         output, _ = capfd.readouterr()

#         expected = """{
#     "fn_a": {
#         "sets": [
#             "a.attr"
#         ],
#         "gets": [
#             "b.attr"
#         ],
#         "dels": [],
#         "calls": []
#     },
#     "fn_b": {
#         "sets": [
#             "c.attr"
#         ],
#         "gets": [
#             "c.some_attr",
#             "c",
#             "c.attr"
#         ],
#         "dels": [],
#         "calls": [
#             "print()",
#             "fn_a()"
#         ]
#     }
# }
# """

#         assert "ExpectedDecoratorAssertor: line 2:" in output
#         assert expected in output
