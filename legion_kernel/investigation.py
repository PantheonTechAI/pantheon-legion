"""Canonical digest for a bounded Mission investigation intent."""

from __future__ import annotations

import hashlib
import json


def intent_digest(*, command_id: str, mission_id: str, organization_id: str,
                  workspace_id: str, objective: str, profile: str) -> str:
    payload = {
        "command_id": command_id,
        "mission_id": mission_id,
        "organization_id": organization_id,
        "workspace_id": workspace_id,
        "objective": objective,
        "profile": profile,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
