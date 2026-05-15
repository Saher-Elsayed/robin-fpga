"""Shared utilities: logging configuration, seeding, JSON/YAML IO."""

from __future__ import annotations

import json
import logging
import os
import random
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np


def setup_logging(level: str = "INFO", log_file: Optional[Path] = None) -> None:
    """Configure root logger with consistent format."""
    fmt = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file is not None:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=fmt,
        handlers=handlers,
        force=True,
    )


def seed_everything(seed: int = 42) -> None:
    """Seed all PRNGs for reproducibility (numpy, random, torch if available)."""
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    except ImportError:
        pass


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML config file (uses PyYAML if available, else json fallback)."""
    path = Path(path)
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f)
    except ImportError:
        if path.suffix == ".json":
            with open(path) as f:
                return json.load(f)
        raise ImportError("PyYAML required to load YAML configs; pip install pyyaml")


def save_yaml(data: dict[str, Any], path: str | Path) -> None:
    """Save a dict as YAML (uses PyYAML if available)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
        with open(path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False, indent=2)
    except ImportError:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


def load_json(path: str | Path) -> dict[str, Any]:
    with open(path) as f:
        return json.load(f)


def save_json(data: dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def ensure_dir(path: str | Path) -> Path:
    """Create a directory if it doesn't exist; return Path."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_device(prefer_gpu: bool = True) -> str:
    """Return 'cuda' if available and requested, else 'cpu'."""
    try:
        import torch
        if prefer_gpu and torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"
