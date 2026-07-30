"""Generate bounded experiment specifications. This module never executes them."""

from __future__ import annotations

from typing import Any


def specifications(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "trap_id": entry["id"],
        "question": f"Does the observed system reproduce trap {entry['id']} under its named conditions?",
        "prerequisites": ["A disposable or explicitly authorised test surface", "Raw output capture"],
        "risk": "low-to-moderate; review the entry before running",
        "expected_duration": "5-30 minutes unless the entry names a soak",
        "service_disruption": "none by default; do not run if the published check is disruptive",
        "request_or_command": entry["check"],
        "control": "Repeat with the suspected variable removed or with the known-good condition.",
        "confirm_criterion": f"The failure signature described by trap {entry['id']} appears under matching conditions.",
        "refute_criterion": "The paired control and test contradict the published failure signature.",
        "raw_artefacts_to_preserve": ["request/configuration", "response/output", "versions", "timestamps"],
        "rollback": "No mutation is prescribed; restore only changes explicitly authorised for the experiment.",
        "human_review_still_required": True,
        "limitations": entry["known_limitations"],
    } for entry in registry["entries"]]

