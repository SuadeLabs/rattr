from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if sys.version_info.major == 3 and sys.version_info.minor >= 11:
    # isort: off
    import tomllib  # type: ignore reportMissingImports
    from tomllib import TOMLDecodeError  # type: ignore reportMissingImports; noqa: F401

    # isort: on
else:
    import tomli as tomllib
    from tomli import TOMLDecodeError  # noqa: F401

if TYPE_CHECKING:
    from typing import Any


# HACK Wrap `tomllib.loads` to handle type hinting on different python versions
def _load_from_file(file: Path) -> dict[str, Any]:
    return tomllib.loads(file.read_text())


def parse_project_toml(
    pyproject_toml: Path | None,
    project_toml_override: Path | None = None,
) -> dict[str, Any]:
    """Return the parsed project toml."""
    if project_toml_override:
        project_toml = project_toml_override
    else:
        project_toml = pyproject_toml

    if project_toml:
        return _load_from_file(project_toml).get("tool", {}).get("rattr", {})

    return {}
