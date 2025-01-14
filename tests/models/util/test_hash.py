from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple
from unittest import mock

import pytest

from rattr.models.util.hash import (
    hash_file_content,
    hash_python_objects_type_and_source_files,
    hash_string,
)

if TYPE_CHECKING:
    from collections.abc import Generator


class HashableObject(NamedTuple):
    x: int
    y: int


@contextmanager
def temporary_file(file_content: str) -> Generator[Path, None, None]:
    with tempfile.NamedTemporaryFile("w", delete=False) as fp:
        filepath = fp.name
        fp.write(file_content)

    yield Path(fp.name)

    os.unlink(filepath)


@pytest.mark.parametrize(
    "s, expected",
    testcases := [
        ("", "d41d8cd98f00b204e9800998ecf8427e"),
        ("s", "03c7c0ace395d80182db07ae2c30f034"),
        ("string", "b45cffe084dd3d20d928bee85e7b0f21"),
    ],
    ids=[t[0] for t in testcases],
)
def test_hash_string(s: str, expected: str):
    assert hash_string(s) == expected


@pytest.mark.posix
@pytest.mark.parametrize(
    "file_content, expected",
    [
        ("", "d41d8cd98f00b204e9800998ecf8427e"),
        ("data", "8d777f385d3dfec8815d20f7496026dc"),
        ("data\nmore data", "6b8f1334efdf839fa3e5d1689f3f9e00"),
    ],
    ids=["the_empty_file", "simple_file", "multi_line_file"],
)
def test_hash_file_content(file_content: str, expected: str):
    with temporary_file(file_content) as filepath:
        assert hash_file_content(filepath) == expected


def test_hash_python_objects_type_and_source_files_empty_list():
    assert (
        hash_python_objects_type_and_source_files([])  # type: ignore[reportUnknownArgumentType]
        == "d41d8cd98f00b204e9800998ecf8427e"
    )


def test_hash_python_objects_type_and_source_files_single_item():
    with temporary_file("foo bar") as filepath:
        with mock.patch(
            "rattr.models.util.hash.inspect.getfile",
            new=lambda _: str(filepath),  # type: ignore[reportUnknownArgumentType]
        ):
            assert (
                hash_python_objects_type_and_source_files([HashableObject(1, 2)])
                == "74025d92bb5077ecb7982552aadada23"
            )


def test_hash_python_objects_type_and_source_files_multiple_items():
    with temporary_file("foo bar") as filepath:
        with mock.patch(
            "rattr.models.util.hash.inspect.getfile",
            new=lambda _: str(filepath),  # type: ignore[reportUnknownArgumentType]
        ):
            assert (
                hash_python_objects_type_and_source_files(
                    [
                        HashableObject(1, 2),
                        HashableObject(3, 4),
                    ]
                )
                == "822cda769d2f8ab410df11a3eca5cec2"
            )


def test_hash_python_objects_type_and_source_files_multiple_items_with_changed_file_content():
    # This test simulates the case in which we have the same set of plugins, but the
    # plugin implementation (source file content) changed, i.e. we are using different
    # versions of the same plugin. This should result in different hashes.

    objs = [
        HashableObject(1, 2),
        HashableObject(3, 4),
    ]

    initial_file_content = "foo bar"
    updated_file_content = "foo bar baz"

    with temporary_file(initial_file_content) as filepath:
        with mock.patch(
            "rattr.models.util.hash.inspect.getfile",
            new=lambda _: str(filepath),  # type: ignore[reportUnknownArgumentType]
        ):
            initial_plugins_hash = hash_python_objects_type_and_source_files(objs)
            assert initial_plugins_hash == "822cda769d2f8ab410df11a3eca5cec2"

    with temporary_file(updated_file_content) as filepath:
        with mock.patch(
            "rattr.models.util.hash.inspect.getfile",
            new=lambda _: str(filepath),  # type: ignore[reportUnknownArgumentType]
        ):
            updated_plugins_hash = hash_python_objects_type_and_source_files(objs)
            assert updated_plugins_hash == "5c916b3b7a370606800014f77c862a75"

    assert initial_plugins_hash != updated_plugins_hash
