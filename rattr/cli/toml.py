from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

try:
    # python >= 3.11
    import tomllib  # type: ignore reportMissingImports
except ImportError:
    # python < 3.11
    import tomli as tomllib


# HACK Wrap `tomllib.loads` to handle type hinting on different python versions
def _load_from_file(file: Path) -> Dict[str, Any]:
    return tomllib.loads(file.read_text())


def parse_toml(config_path: Path) -> Dict[str, Any]:
    """Return the parsed toml config."""
    cfg, cleaned_cfg = _load_from_file(config_path).get("tool", {}).get("rattr", {}), {}

    for k, v in cfg.items():
        if k.startswith("--"):
            k = k[2:]
        elif k.startswith("-"):
            k = k[1:]
        cleaned_cfg[k] = v

    return cleaned_cfg
