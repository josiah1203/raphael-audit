"""Default filesystem paths for Calliope."""

from __future__ import annotations

from pathlib import Path


def calliope_home() -> Path:
    return Path.home() / ".calliope"


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


def default_graph_db_path() -> Path:
    return calliope_home() / "graph.db"
