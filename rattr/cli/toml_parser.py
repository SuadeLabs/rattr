from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import tomli as tomllib


def load_config_from_project_toml(expected_fields: Tuple[str] = ()) -> Dict[str, Any]:
    """
    Function finds project toml and parses it into a toml config dictionary
    while only keeping expected fields (if expected fields is empty then
    keep all fields).
    """
    toml_cfg_path = find_project_toml()
    if toml_cfg_path:
        return parse_project_toml(
            config_path=toml_cfg_path, expected_fields=expected_fields
        )
    return {}


def find_project_root() -> Optional[Path]:
    """
    Function finds project root by starting search from cwd and
    then exploring parent directories until it finds
    pyproject.toml or .git or .hg file.
    """
    srcs = [str(Path.cwd().resolve())]
    path_srcs = [Path(Path.cwd(), src).resolve() for src in srcs]
    src_parents = [
        list(path.parents) + ([path] if path.is_dir() else []) for path in path_srcs
    ]
    common_base = max(
        set.intersection(*(set(parents) for parents in src_parents)),
        key=lambda path: path.parts,
    )
    for directory in (common_base, *common_base.parents):
        if (
            (directory / ".git").exists()
            or (directory / ".hg").is_dir()
            or (directory / "pyproject.toml").is_file()
        ):
            return directory
    return None


def find_project_toml() -> Optional[str]:
    """
    Function finds pyproject.toml file by finding project root
    first then looking pyproject.toml there.
    """
    path_project_root = find_project_root()
    if not path_project_root:
        return None
    path_pyproject_toml = path_project_root / "pyproject.toml"
    if path_pyproject_toml.is_file():
        return str(path_pyproject_toml)
    return None


def parse_project_toml(
    config_path: str, expected_fields: Tuple[str] = ()
) -> Dict[str, Any]:
    """
    Function parses pyproject.toml file into a cfg dictionary
    while only keeping expected fields (if expected fields is empty
    then keep all fields).
    """
    with open(config_path, "rb") as f:
        pyproject_toml_cfg = tomllib.load(f)
    cfg = pyproject_toml_cfg.get("tool", {}).get("rattr", {})
    cfg_dict = {}
    for k, v in cfg.items():
        if expected_fields and k not in expected_fields:
            continue
        if k.startswith("--"):
            k = k[2:]
        elif k.startswith("-"):
            k = k[1:]
        cfg_dict[k] = v
    return cfg_dict
