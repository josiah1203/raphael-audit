"""Core validation, storage, and fidelity scoring for Calliope."""

from raphael_audit.core.checksum import compute_checksum
from raphael_audit.core.event_builder import build_geometry_event
from raphael_audit.core.fidelity import score_fidelity
from raphael_audit.core.paths import default_config_path, default_db_path
from raphael_audit.core.store import EventStore
from raphael_audit.core.uuid7 import uuid7_str

__all__ = [
    "EventStore",
    "build_geometry_event",
    "compute_checksum",
    "default_config_path",
    "default_db_path",
    "score_fidelity",
    "uuid7_str",
]
