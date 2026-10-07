"""Unified diagnosis across registry matching, offline scans, and live Doctor probes.

The orchestrator deliberately keeps evidence classes separate:
- symptom similarity is a lead;
- file-scan findings are static/log leads;
- Doctor findings are bounded live observations.

It never upgrades a text/file resemblance into confirmation.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Sequence

from .api import detect_target, plan_checks, result_to_doctor_json, run_checks
from .coverage import build_coverage
from .matching import diagnose
from .scan import scan


def _ids_from_finding(finding: dict[str, Any]) -> list[str]:
    values = finding.get("traps")
    if not values:
        one = finding.get("trap_id")
        values = [one] if one is not None else []
    return [str(value).zfill(2) for value in values if value is not None]


def diagnose_environment(
    registry: dict[str, Any],
    symptom: str = "",
    *,
    paths: Sequence[str] | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    stack: str | None = None,
    model: str | None = None,
    version: str | None = None,
    hf_repo: str | None = None,
    log_excerpt: str | None = None,
    limit: int = 5,
    mode: str = "lite",
    max_requests: int | None = None,
    allowed_roots: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Consider the full registry, then fuse only evidence the caller supplied.

    mode=lite defaults to a five-request live budget. mode=doctor keeps the
    Doctor catalogue semantics and has no implicit request cap.
    """
    entries = registry.get("entries") or []
    by_id = {str(entry["id"]).zfill(2): entry for entry in entries}
    coverage = build_coverage(registry)["summary"]
    files = list(paths or [])

    file_report = scan(files, list(allowed_roots) if allowed_roots is not None else None) if files else None

    target = None
    effective_stack = stack
    effective_model = model
    live_warning = None
    if base_url:
        target = detect_target(
            base_url,
            api_key=api_key,
            model=model,
            hf_repo=hf_repo,
        )
        if target.reachable:
            effective_stack = stack or (target.stack if target.stack != "unknown" else None)
            effective_model = model or target.model
        else:
            live_warning = "Endpoint detection could not reach /v1/models; no live probes ran."

    symptom_result = diagnose(
        registry,
        symptom or "",
        stack=effective_stack,
        model=effective_model,
        version=version,
        log_excerpt=log_excerpt,
        limit=max(1, max(limit, 10)),
    )

    preferred: list[str] = []
    for match in symptom_result.get("matches") or []:
        preferred.extend(str(t).zfill(2) for t in (match.get("trap_ids") or []))
    if file_report:
        preferred.extend(str(t).zfill(2) for t in (file_report.get("traps") or []))
    preferred = list(dict.fromkeys(preferred))

    live_result = None
    if target is not None and target.reachable:
        budget = max_requests
        if mode == "lite" and budget is None:
            budget = 5
        plan = plan_checks(
            target=target,
            mode=mode,
            max_requests=budget,
            hf_repo=hf_repo,
            preferred_trap_ids=preferred,
        )
        run = run_checks(plan, api_key=api_key, hf_repo=hf_repo, model=effective_model)
        live_result = result_to_doctor_json(run)
        live_result["target"] = {
            "stack": target.stack,
            "model": target.model,
            "build": target.build,
            "reachable": target.reachable,
            "capabilities": list(target.capabilities),
            "notes": list(target.notes),
        }
        live_result["selected_probe_detail"] = [
            {
                "id": probe.id,
                "traps": list(probe.traps),
                "request_cost": probe.request_cost,
                "reason": probe.reason,
            }
            for probe in plan.selected
        ]

    candidates: dict[str, dict[str, Any]] = {}

    def row(trap_id: str) -> dict[str, Any]:
        trap_id = str(trap_id).zfill(2)
        if trap_id not in candidates:
            entry = by_id.get(trap_id, {})
            candidates[trap_id] = {
                "trap_id": trap_id,
                "title": entry.get("title", ""),
                "source_path": entry.get("source_path"),
                "evidence_status": entry.get("evidence_status"),
                "confirmation_check": entry.get("check", ""),
                "signals": [],
                "_score": 0.0,
            }
        return candidates[trap_id]

    for rank, match in enumerate(symptom_result.get("matches") or [], 1):
        for trap_id in match.get("trap_ids") or []:
            item = row(trap_id)
            item["signals"].append({
                "kind": "symptom_match",
                "rank": rank,
                "evidence_weight": match.get("evidence_weight"),
                "log_signature": match.get("log_signature"),
            })
            item["_score"] += max(5.0, 35.0 - (rank * 3.0))
            item["_score"] += min(10.0, float(match.get("evidence_weight") or 0.0))

    if file_report:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for finding in file_report.get("findings") or []:
            grouped.setdefault(str(finding.get("trap_id")).zfill(2), []).append(finding)
        for trap_id, findings in grouped.items():
            item = row(trap_id)
            item["signals"].append({
                "kind": "file_scan",
                "finding_count": len(findings),
                "detectors": sorted({str(f.get("detector") or "") for f in findings}),
                "files": sorted({str(f.get("file") or "") for f in findings})[:8],
            })
            item["_score"] += 45.0 + min(10.0, len(findings))

    checked_clean: set[str] = set()
    live_unknown: set[str] = set()
    if live_result:
        for finding in live_result.get("findings") or []:
            level = str(finding.get("level") or "")
            for trap_id in _ids_from_finding(finding):
                if level == "OK":
                    checked_clean.add(trap_id)
                    if trap_id in candidates:
                        candidates[trap_id]["signals"].append({
                            "kind": "live_probe",
                            "level": level,
                            "code": finding.get("code"),
                        })
                        candidates[trap_id]["_score"] -= 20.0
                    continue
                if level == "UNKNOWN":
                    live_unknown.add(trap_id)
                item = row(trap_id)
                item["signals"].append({
                    "kind": "live_probe",
                    "level": level,
                    "code": finding.get("code"),
                    "title": finding.get("title"),
                    "detail": finding.get("detail"),
                })
                if level == "PROBLEM":
                    item["_score"] += 120.0
                elif level == "INCONCLUSIVE":
                    item["_score"] += 30.0
                elif level == "UNKNOWN":
                    item["_score"] += 5.0

    ranked = sorted(
        candidates.values(),
        key=lambda item: (-float(item["_score"]), int(item["trap_id"])),
    )
    for item in ranked:
        item["score"] = round(float(item.pop("_score")), 2)
        kinds = {signal["kind"] for signal in item["signals"]}
        live_problem = any(
            signal.get("kind") == "live_probe" and signal.get("level") == "PROBLEM"
            for signal in item["signals"]
        )
        if live_problem:
            item["evidence_level"] = "live_probe_problem"
        elif len(kinds) >= 2:
            item["evidence_level"] = "multi_signal_lead"
        elif "file_scan" in kinds:
            item["evidence_level"] = "file_scan_lead"
        else:
            item["evidence_level"] = "symptom_lead"

    selected_probe_traps: set[str] = set()
    if live_result:
        for probe in live_result.get("selected_probe_detail") or []:
            selected_probe_traps.update(str(t).zfill(2) for t in probe.get("traps") or [])

    warnings = [
        "Every canonical trap was considered for routing, but only implemented detectors/probes can test it automatically.",
        "Symptom and file-scan matches are leads, not confirmations.",
    ]
    if live_warning:
        warnings.append(live_warning)

    return {
        "kind": "unified_diagnosis",
        "registry_traps_considered": len(entries),
        "automatic_coverage": coverage,
        "inputs": {
            "symptom_supplied": bool((symptom or "").strip()),
            "paths_supplied": len(files),
            "endpoint_supplied": bool(base_url),
            "mode": mode,
            "max_requests": max_requests if max_requests is not None else (5 if mode == "lite" else None),
        },
        "detected_target": asdict(target) if target is not None else None,
        "symptom_diagnosis": symptom_result,
        "file_scan": file_report,
        "live_doctor": live_result,
        "candidate_traps": ranked[: max(1, limit)],
        "live_checked_clean_traps": sorted(checked_clean, key=int),
        "live_could_not_check_traps": sorted(live_unknown, key=int),
        "live_selected_probe_traps": sorted(selected_probe_traps, key=int),
        "warnings": warnings,
    }
