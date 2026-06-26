"""Default filesystem paths for Raphael / Calliope-compat storage."""

from __future__ import annotations

import os
from pathlib import Path


def calliope_home() -> Path:
  """Compat alias — prefer RAPHAEL_HOME when set."""
  return raphael_home()


def raphael_home() -> Path:
    return Path(os.environ.get("RAPHAEL_HOME", Path.home() / ".raphael"))


def default_db_path() -> Path:
    return calliope_home() / "events.db"


def default_config_path() -> Path:
    return calliope_home() / "config.yaml"


def default_objects_path() -> Path:
    return calliope_home() / "objects"


def default_silver_db_path() -> Path:
    return calliope_home() / "silver.db"


def default_graph_db_path() -> Path:
    return calliope_home() / "graph.db"
