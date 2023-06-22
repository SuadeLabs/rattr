from __future__ import annotations

from rattr.versioning._util import is_python_version

if is_python_version(">=3.10"):
    from typing import TypeAlias  # noqa: F401
else:
    from typing_extensions import TypeAlias  # noqa: F401
