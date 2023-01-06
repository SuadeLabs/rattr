from typing import Dict, Any, Optional
import tomli as tomllib
from pathlib import Path


def load_config_from_project_toml() -> Optional[Dict]:
    toml_cfg_path = find_project_toml()
    if toml_cfg_path:
        return parse_project_toml(config_path=toml_cfg_path)
    return None


def find_project_root() -> Optional[Path]:
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
    path_project_root = find_project_root()
    if not path_project_root:
        return None
    path_pyproject_toml = path_project_root / "pyproject.toml"
    if path_pyproject_toml.is_file():
        return str(path_pyproject_toml)
    return None


def parse_project_toml(config_path: str) -> Dict[str, Any]:
    with open(config_path, "rb") as f:
        pyproject_toml_cfg = tomllib.load(f)
    cfg = pyproject_toml_cfg.get("tool", {}).get("ruff", {})
    return {k.replace("--", "").replace("-", "_"): v for k, v in cfg.items()}
