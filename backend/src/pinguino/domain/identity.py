"""Canonical serialization and content identifiers.

Identifiers must stay stable across processes and orderings, so JSON is emitted with
sorted keys, no insignificant whitespace and explicit UTF-8.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel

CONTENT_ID_LENGTH = 32


def canonical_json(payload: Any) -> str:
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(payload: Any) -> str:
    """Full SHA-256 of the canonical form, used for dataset and export integrity."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def content_id(prefix: str, payload: Any) -> str:
    """Short, prefixed, human-readable identifier derived from the content hash."""
    return f"{prefix}-{content_hash(payload)[:CONTENT_ID_LENGTH]}"
