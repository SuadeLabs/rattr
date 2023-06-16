from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if sys.version_info.major == 3 and sys.version_info.minor >= 11:
    import tomllib  # type: ignore reportMissingImports
    from tomllib import TOMLDecodeError  # type: ignore reportMissingImports; noqa: F401
else:
    import tomli as tomllib
    from tomli import TOMLDecodeError  # noqa: F401

if TYPE_CHECKING:
    from typing import Any, Dict, Optional


# HACK Wrap `tomllib.loads` to handle type hinting on different python versions
def _load_from_file(file: Path) -> Dict[str, Any]:
    return tomllib.loads(file.read_text())


def parse_toml(config_path: Path) -> Dict[str, Any]:
    """Return the parsed toml config.

    Raises:
        TOMLDecodeError: Raised on invalid toml syntax.
    """
    cfg, cleaned_cfg = _load_from_file(config_path).get("tool", {}).get("rattr", {}), {}

    for k, v in cfg.items():
        if k.startswith("--"):
            k = k[2:]
        elif k.startswith("-"):
            k = k[1:]
        cleaned_cfg[k] = v

    return cleaned_cfg


def parse_project_toml(
    pyproject_toml: Optional[Path],
    project_toml_override: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return the parsed project toml."""
    if project_toml_override:
        project_toml = project_toml_override
    else:
        project_toml = pyproject_toml

    if project_toml:
        return parse_toml(project_toml)

    return {}
