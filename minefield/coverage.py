"""Truthful overlapping coverage by diagnostic modality."""

from __future__ import annotations

from typing import Any

from .guided_experiments import specifications
from .log_inspector import IMPLEMENTED_TRAPS as LOG_TRAPS
from .model_inspector import IMPLEMENTED_TRAPS as MODEL_TRAPS
from .results_inspector import IMPLEMENTED_TRAPS as RESULTS_TRAPS
from .static_inspector import IMPLEMENTED_TRAPS as CONFIG_TRAPS
from .template_inspector import IMPLEMENTED_TRAPS as TEMPLATE_TRAPS

# Offline file checks, all read-only over files the user names. The
# "static_config" modality covers every one of them; which module fires is
# recorded per trap so a reader can find the rule.
OFFLINE_CHECKERS = (
    ("minefield.static_inspector", CONFIG_TRAPS),
    ("minefield.template_inspector", TEMPLATE_TRAPS),
    ("minefield.model_inspector", MODEL_TRAPS),
    ("minefield.results_inspector", RESULTS_TRAPS),
)
STATIC_TRAPS = frozenset().union(*(traps for _, traps in OFFLINE_CHECKERS))


def _offline_checker(trap_id: str) -> str | None:
    names = [name for name, traps in OFFLINE_CHECKERS if trap_id in traps]
    return ", ".join(names) if names else None


def build_coverage(registry: dict[str, Any]) -> dict[str, Any]:
    experiments = {item["trap_id"]: item for item in specifications(registry)}
    traps = []
    for entry in registry["entries"]:
        trap_id = entry["id"]
        endpoint = entry["doctor_coverage"]["implemented"]
        modalities = {
            "endpoint_probe": {
                "state": "implemented" if endpoint else "not_yet_designed",
                "implemented_checker": "doctor/minefield_doctor.py" if endpoint else None,
                "required_inputs": ["OpenAI-compatible base URL"] if endpoint else [],
                "safety_level": "bounded read-only requests",
                "expected_duration": "under one minute",
                "can_prove_clean": bool(endpoint),
                "possible_match_only": not endpoint,
                "confirm_criterion": entry["check"],
                "refute_criterion": "Only a trap-specific clean contract may refute the named failure.",
                "limitations": entry["known_limitations"],
            },
            "static_config": {
                "state": "implemented" if trap_id in STATIC_TRAPS else "possible",
                "implemented_checker": _offline_checker(trap_id),
                "required_inputs": ["Explicitly supplied files: configs, launch scripts, model folder, "
                                    "chat template or eval results"],
                "safety_level": "read-only",
                "expected_duration": "seconds",
                "can_prove_clean": False,
                "possible_match_only": True,
                "confirm_criterion": entry["check"],
                "refute_criterion": "Compare with the effective runtime configuration.",
                "limitations": "Static configuration does not prove the live process used it.",
            },
            "log_scan": {
                "state": "implemented" if trap_id in LOG_TRAPS else "possible",
                "implemented_checker": "minefield.log_inspector" if trap_id in LOG_TRAPS else None,
                "required_inputs": ["Explicitly supplied bounded log files"],
                "safety_level": "read-only",
                "expected_duration": "seconds",
                "can_prove_clean": False,
                "possible_match_only": True,
                "confirm_criterion": entry["check"],
                "refute_criterion": "Show a later recovery or a contradictory control.",
                "limitations": "Absence of a signature is not proof of safety.",
            },
            "guided_experiment": {
                "state": "specified",
                "implemented_checker": None,
                "required_inputs": experiments[trap_id]["prerequisites"],
                "safety_level": experiments[trap_id]["risk"],
                "expected_duration": experiments[trap_id]["expected_duration"],
                "can_prove_clean": False,
                "possible_match_only": True,
                "confirm_criterion": experiments[trap_id]["confirm_criterion"],
                "refute_criterion": experiments[trap_id]["refute_criterion"],
                "limitations": experiments[trap_id]["limitations"],
            },
            "human_review": {
                "state": "possible",
                "implemented_checker": None,
                "required_inputs": ["Exact stack, model, versions, and preserved evidence"],
                "safety_level": "read-only comparison",
                "expected_duration": "variable",
                "can_prove_clean": False,
                "possible_match_only": True,
                "confirm_criterion": "A reviewer verifies the trap's exact conditions and criterion.",
                "refute_criterion": "A reviewer verifies a condition mismatch or contrary control.",
                "limitations": "Human review retains the published evidence status.",
            },
        }
        traps.append({"id": trap_id, "modalities": modalities})
    summary = {
        "total_canonical_traps": len(traps),
        "endpoint_checks_implemented": sum(
            item["modalities"]["endpoint_probe"]["state"] == "implemented" for item in traps
        ),
        "static_checks_implemented": len(STATIC_TRAPS),
        "log_checks_implemented": len(LOG_TRAPS),
        "any_automated_check": sum(
            item["modalities"]["endpoint_probe"]["state"] == "implemented"
            or item["id"] in STATIC_TRAPS or item["id"] in LOG_TRAPS
            for item in traps
        ),
        "guided_experiments_specified": len(experiments),
        "human_review_possible": len(traps),
        "counts_overlap": True,
    }
    return {"schema_version": "1.0", "summary": summary, "traps": traps}
