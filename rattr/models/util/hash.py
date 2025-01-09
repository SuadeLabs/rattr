from __future__ import annotations

import hashlib
import inspect
from os.path import isfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import TypeVar

    T = TypeVar("T")


def hash_python_objects_type_and_source_files(
    objects: Sequence[T],
    /,
    *,
    name_of_object: Callable[[T], str] = lambda o: getattr(o, "__name__", str(o)),
) -> str:
    """Return the hash of the list of objects and their source file definitions.

    ### Note
    This is intrinsically imperfect as the source file's imports are not checked. Doing
    so would be out-of-scope for now and would introduce performance considerations.
    This approach should be more than sufficient as the only things most plugin
    definitions should import are the stdlib and rattr.
    """
    hash = hashlib.md5()

    for obj in sorted(objects, key=lambda o: name_of_object(o)):
        # Hash object name...
        hash.update(name_of_object(obj).encode("utf-8"))

        # ... and definition (source file content)
        obj_source_file = Path(inspect.getfile(type(obj))).resolve()
        with obj_source_file.open("rb") as f:
            while True:
                buffer = f.read(2**20)

                if not buffer:
                    break

                hash.update(buffer)

    return hash.hexdigest()


def hash_file_content(
    filepath: str | Path,
    *,
    blocksize: int = 2**20,
) -> str:
    """Return the hash of the given file's content."""
    hash = hashlib.md5()

    if not isfile(filepath):
        return hash.hexdigest()

    with open(filepath, "rb") as f:
        while True:
            buffer = f.read(blocksize)

            if not buffer:
                break

            hash.update(buffer)

    return hash.hexdigest()


def hash_string(s: str, /) -> str:
    """Return the hash of the given string."""
    hash = hashlib.md5()
    hash.update(s.encode("utf-8"))
    return hash.hexdigest()
