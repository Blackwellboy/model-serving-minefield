"""Reusable Doctor planning/execution API (Phase 0).

Agent-/framework-neutral. Public surface:
  detect_target(...)
  plan_checks(...)
  run_checks(...)
  summarize(...)

``plan_checks`` issues zero chat completions.
``run_checks`` enforces a hard request budget when provided.
Trap markdown is never executed as code.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Mapping, Optional, Sequence

from .registry import ROOT

__all__ = [
    "RequestBudgetExceeded",
    "TargetInfo",
    "PlannedProbe",
    "SkippedProbe",
    "ProbePlan",
    "RunResult",
    "Summary",
    "detect_target",
    "plan_checks",
    "run_checks",
    "summarize",
    "result_to_doctor_json",
]


class RequestBudgetExceeded(RuntimeError):
    """Re-exported conceptually; actual raise comes from doctor module."""


@dataclass(frozen=True)
class TargetInfo:
    base_url: str
    root_url: str
    stack: str = "unknown"
    model: Optional[str] = None
    build: Optional[str] = None
    reachable: bool = True
    capabilities: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlannedProbe:
    id: str
    traps: tuple[str, ...]
    request_cost: int
    title: str
    lite_eligible: bool
    requires: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class SkippedProbe:
    id: str
    traps: tuple[str, ...]
    request_cost: int
    title: str
    reason: str


@dataclass(frozen=True)
class ProbePlan:
    mode: str
    max_requests: Optional[int]
    target: TargetInfo
    selected: tuple[PlannedProbe, ...]
    skipped: tuple[SkippedProbe, ...]
    expected_requests: int
    fits_budget: bool
    minefield_notes: tuple[str, ...] = ()

    @property
    def selected_ids(self) -> tuple[str, ...]:
        return tuple(p.id for p in self.selected)


@dataclass
class RunResult:
    plan: ProbePlan
    stack: str
    model: Optional[str]
    requests_planned: int
    requests_executed: int
    request_budget: Optional[int]
    findings: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    coverage: dict[str, Any] = field(default_factory=dict)
    coverage_line: str = ""
    budget_exceeded: bool = False
    error: Optional[str] = None
    reachable: bool = True


@dataclass(frozen=True)
class SummaryFinding:
    level: str
    code: str
    traps: tuple[str, ...]
    title: str
    detail: Optional[str]


@dataclass(frozen=True)
class Summary:
    clean_count: int
    problem_count: int
    inconclusive_count: int
    unknown_count: int
    skipped_probe_count: int
    requests_made: int
    request_budget: Optional[int]
    trap_ids_clean: tuple[str, ...]
    trap_ids_problem: tuple[str, ...]
    trap_ids_inconclusive: tuple[str, ...]
    trap_ids_unknown: tuple[str, ...]
    findings: tuple[SummaryFinding, ...]
    coverage_line: str
    human_lines: tuple[str, ...]


_doctor_mod = None


def _load_doctor():
    """Load the first-party doctor module (repo path or packaged data copy)."""
    global _doctor_mod
    if _doctor_mod is not None:
        return _doctor_mod
    candidates = [
        ROOT / "doctor" / "minefield_doctor.py",
        Path(__file__).resolve().parent / "data" / "minefield_doctor.py",
    ]
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        raise FileNotFoundError("minefield_doctor.py not found")
    spec = importlib.util.spec_from_file_location("minefield_doctor_api", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load doctor from {path}")
    mod = importlib.util.module_from_spec(spec)
    # Ensure the module is importable under a stable name for relative lookups.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    _doctor_mod = mod
    return mod


def _normalize_base(base_url: str) -> tuple[str, str]:
    base = (base_url or "").rstrip("/")
    if not base:
        raise ValueError("base_url is required")
    if not base.endswith("/v1"):
        base = base + "/v1"
    root = base[:-3].rstrip("/")
    return base, root


def _capabilities_for_stack(stack: str, *, hf_repo: Optional[str], explicit: Optional[Iterable[str]]) -> tuple[str, ...]:
    caps: set[str] = {"streaming"}  # OpenAI-compatible chat streams are assumed available to probe
    # Tools/multimodal are probed opportunistically; treat as available unless caller disables.
    caps.add("tools")
    if explicit is not None:
        return tuple(sorted(set(explicit)))
    if stack in {"llamacpp", "vllm", "sglang", "ollama", "unknown", "openai-compatible"}:
        caps.add("tools")
    if hf_repo:
        caps.add("hf_repo")
    # multimodal optional — include as capability only if caller asks; default off for lite
    return tuple(sorted(caps))


def detect_target(
    base_url: str,
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    hf_repo: Optional[str] = None,
    capabilities: Optional[Iterable[str]] = None,
) -> TargetInfo:
    """Detect stack/model via GET probes only (no chat completions)."""
    md = _load_doctor()
    base, root = _normalize_base(base_url)
    doc = md.Doc()
    ok = md.detect_stack(doc, base, root, api_key)
    if model:
        doc.model = model
    notes: list[str] = []
    if not ok:
        return TargetInfo(
            base_url=base,
            root_url=root,
            stack="unknown",
            model=model,
            reachable=False,
            capabilities=(),
            notes=("unreachable:/v1/models",),
        )
    caps = _capabilities_for_stack(doc.stack, hf_repo=hf_repo, explicit=capabilities)
    if doc.stack == "unknown":
        notes.append("stack_unidentified")
    return TargetInfo(
        base_url=base,
        root_url=root,
        stack=str(doc.stack or "unknown"),
        model=doc.model,
        build=getattr(doc, "build", None),
        reachable=True,
        capabilities=caps,
        notes=tuple(notes),
    )


def _probe_meta(md) -> list[Any]:
    return list(md.PROBE_SPECS)


def _requires_met(requires: Sequence[str], capabilities: Sequence[str]) -> bool:
    if not requires:
        return True
    have = set(capabilities)
    return all(r in have for r in requires)


def plan_checks(
    *,
    target: Optional[TargetInfo] = None,
    base_url: Optional[str] = None,
    mode: str = "lite",
    max_requests: Optional[int] = None,
    capabilities: Optional[Iterable[str]] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    hf_repo: Optional[str] = None,
    detect: bool = False,
) -> ProbePlan:
    """Build a deterministic probe plan. Issues zero chat completions.

    By default does not contact the network. Pass ``detect=True`` (or a
    precomputed ``target``) to include stack detection metadata; detection
    uses GET only, never chat completions.
    """
    mode_norm = (mode or "lite").strip().lower()
    if mode_norm not in {"lite", "doctor"}:
        raise ValueError("mode must be 'lite' or 'doctor'")

    if target is None:
        if detect:
            if not base_url:
                raise ValueError("base_url required when detect=True")
            target = detect_target(
                base_url, api_key=api_key, model=model, hf_repo=hf_repo, capabilities=capabilities
            )
        else:
            base, root = _normalize_base(base_url or "http://127.0.0.1:0/v1")
            caps = _capabilities_for_stack(
                "unknown", hf_repo=hf_repo, explicit=capabilities
            )
            if hf_repo:
                caps = tuple(sorted(set(caps) | {"hf_repo"}))
            target = TargetInfo(
                base_url=base,
                root_url=root,
                stack="unknown",
                model=model,
                capabilities=caps,
                notes=("plan_without_detect",),
            )
    elif capabilities is not None:
        target = TargetInfo(
            **{
                **asdict(target),
                "capabilities": tuple(sorted(set(capabilities))),
            }
        )
    elif hf_repo and "hf_repo" not in target.capabilities:
        target = TargetInfo(
            **{
                **asdict(target),
                "capabilities": tuple(sorted(set(target.capabilities) | {"hf_repo"})),
            }
        )

    md = _load_doctor()
    specs = _probe_meta(md)

    budget = max_requests
    if mode_norm == "lite" and budget is None:
        budget = 5
    if budget is not None and budget < 0:
        raise ValueError("max_requests must be >= 0")

    selected: list[PlannedProbe] = []
    skipped: list[SkippedProbe] = []
    used = 0

    if mode_norm == "doctor":
        candidates = list(specs)
    else:
        # Lite: eligible probes only, highest priority first, then catalog order.
        candidates = sorted(
            [s for s in specs if s.lite_eligible],
            key=lambda s: (-s.lite_priority, s.id),
        )

    for spec in candidates:
        # Doctor mode preserves historical behaviour: every catalog probe runs;
        # individual checks still self-skip when preconditions fail. Lite mode
        # filters on declared requires so budgets stay meaningful.
        if mode_norm == "lite" and not _requires_met(spec.requires, target.capabilities):
            skipped.append(
                SkippedProbe(
                    id=spec.id,
                    traps=tuple(spec.traps),
                    request_cost=spec.request_cost,
                    title=spec.title,
                    reason=f"missing_capabilities:{','.join(spec.requires)}",
                )
            )
            continue
        cost = int(spec.request_cost)
        if budget is not None and used + cost > budget:
            skipped.append(
                SkippedProbe(
                    id=spec.id,
                    traps=tuple(spec.traps),
                    request_cost=spec.request_cost,
                    title=spec.title,
                    reason=f"exceeds_budget:need={cost},remaining={budget - used}",
                )
            )
            continue
        reason = "doctor_catalog_order" if mode_norm == "doctor" else f"lite_priority={spec.lite_priority}"
        selected.append(
            PlannedProbe(
                id=spec.id,
                traps=tuple(spec.traps),
                request_cost=cost,
                title=spec.title,
                lite_eligible=bool(spec.lite_eligible),
                requires=tuple(spec.requires),
                reason=reason,
            )
        )
        used += cost

    if mode_norm == "lite":
        for spec in specs:
            if any(s.id == spec.id for s in selected) or any(s.id == spec.id for s in skipped):
                continue
            reason = "not_lite_eligible" if not spec.lite_eligible else "not_selected"
            skipped.append(
                SkippedProbe(
                    id=spec.id,
                    traps=tuple(spec.traps),
                    request_cost=spec.request_cost,
                    title=spec.title,
                    reason=reason,
                )
            )

    fits = True if budget is None else used <= budget
    notes = list(target.notes)
    if mode_norm == "lite":
        notes.append("lite_does_not_pad_to_budget")
    return ProbePlan(
        mode=mode_norm,
        max_requests=budget,
        target=target,
        selected=tuple(selected),
        skipped=tuple(skipped),
        expected_requests=used,
        fits_budget=fits,
        minefield_notes=tuple(notes),
    )


def run_checks(
    plan: ProbePlan,
    *,
    api_key: Optional[str] = None,
    hf_repo: Optional[str] = None,
    hf_revision: str = "main",
    model: Optional[str] = None,
) -> RunResult:
    """Execute a previously constructed plan in-process with a hard budget."""
    md = _load_doctor()
    BudgetExc = getattr(md, "RequestBudgetExceeded", RuntimeError)

    target = plan.target
    if not target.reachable and "plan_without_detect" not in target.notes:
        return RunResult(
            plan=plan,
            stack=target.stack,
            model=target.model,
            requests_planned=plan.expected_requests,
            requests_executed=0,
            request_budget=plan.max_requests,
            reachable=False,
            error="target_unreachable",
        )

    # Optional live detect when plan was offline
    base, root = target.base_url, target.root_url
    doc = md.Doc(request_budget=plan.max_requests)
    if not md.detect_stack(doc, base, root, api_key):
        return RunResult(
            plan=plan,
            stack="unknown",
            model=model or target.model,
            requests_planned=plan.expected_requests,
            requests_executed=0,
            request_budget=plan.max_requests,
            reachable=False,
            error="unreachable:/v1/models",
        )
    if model or target.model:
        doc.model = model or target.model

    args = SimpleNamespace(
        base_url=base,
        api_key=api_key,
        model=doc.model,
        hf_repo=hf_repo,
        hf_revision=hf_revision,
        report=False,
        json=None,
    )

    budget_exceeded = False
    err = None
    try:
        md.run(doc, base, root, args, only_ids=list(plan.selected_ids))
    except BudgetExc as exc:
        budget_exceeded = True
        err = str(exc)

    cov = md.coverage(doc)
    return RunResult(
        plan=plan,
        stack=str(doc.stack),
        model=doc.model,
        requests_planned=plan.expected_requests,
        requests_executed=int(doc.requests_made),
        request_budget=plan.max_requests,
        findings=list(doc.findings),
        evidence=dict(doc.evidence),
        coverage=cov,
        coverage_line=md.coverage_line(cov),
        budget_exceeded=budget_exceeded,
        error=err,
        reachable=True,
    )


def summarize(result: RunResult) -> Summary:
    """Structured summary — no quality/intelligence score."""
    findings = result.findings or []

    def _level(level: str) -> list[dict[str, Any]]:
        return [f for f in findings if f.get("level") == level]

    def _traps(level: str) -> tuple[str, ...]:
        out: set[str] = set()
        for f in _level(level):
            for t in f.get("traps") or []:
                out.add(str(t))
        return tuple(sorted(out))

    summary_findings = tuple(
        SummaryFinding(
            level=str(f.get("level")),
            code=str(f.get("code") or ""),
            traps=tuple(str(t) for t in (f.get("traps") or [])),
            title=str(f.get("title") or ""),
            detail=f.get("detail"),
        )
        for f in findings
    )

    lines: list[str] = []
    if result.coverage_line:
        lines.append(result.coverage_line)
    lines.append(
        f"requests_made={result.requests_executed}"
        + (f" budget={result.request_budget}" if result.request_budget is not None else "")
    )
    for label, level in (
        ("PROBLEMS", "PROBLEM"),
        ("CLEAN", "OK"),
        ("INCONCLUSIVE", "INCONCLUSIVE"),
        ("COULD NOT CHECK", "UNKNOWN"),
    ):
        group = _level(level)
        if not group:
            continue
        lines.append(f"{label} ({len(group)}):")
        for f in group:
            traps = ",".join(str(t) for t in (f.get("traps") or [])) or "-"
            lines.append(f"  [{traps}] {f.get('title')}")

    return Summary(
        clean_count=len(_level("OK")),
        problem_count=len(_level("PROBLEM")),
        inconclusive_count=len(_level("INCONCLUSIVE")),
        unknown_count=len(_level("UNKNOWN")),
        skipped_probe_count=len(result.plan.skipped),
        requests_made=result.requests_executed,
        request_budget=result.request_budget,
        trap_ids_clean=_traps("OK"),
        trap_ids_problem=_traps("PROBLEM"),
        trap_ids_inconclusive=_traps("INCONCLUSIVE"),
        trap_ids_unknown=_traps("UNKNOWN"),
        findings=summary_findings,
        coverage_line=result.coverage_line,
        human_lines=tuple(lines),
    )


def result_to_doctor_json(result: RunResult) -> dict[str, Any]:
    """JSON object compatible with doctor --json shape (plus plan metadata)."""
    findings = result.findings

    def _by(level: str):
        return [f for f in findings if f.get("level") == level]

    payload = {
        "stack": result.stack,
        "model": result.model,
        "requests_made": result.requests_executed,
        "coverage": result.coverage,
        "coverage_line": result.coverage_line,
        "findings": findings,
        "problems": [
            (f.get("traps"), f.get("title"), f.get("detail")) for f in _by("PROBLEM")
        ],
        "clean": [(f.get("traps"), f.get("title")) for f in _by("OK")],
        "inconclusive": [
            (f.get("traps"), f.get("title"), f.get("detail")) for f in _by("INCONCLUSIVE")
        ],
        "could_not_check": [
            (f.get("traps"), f.get("title"), f.get("detail")) for f in _by("UNKNOWN")
        ],
        "evidence": result.evidence,
        # Additive Phase-0 fields (non-breaking for readers of classic keys):
        "requests_planned": result.requests_planned,
        "request_budget": result.request_budget,
        "plan_mode": result.plan.mode,
        "selected_probes": [p.id for p in result.plan.selected],
        "skipped_probes": [
            {"id": s.id, "reason": s.reason} for s in result.plan.skipped
        ],
    }
    return payload


def summary_to_dict(summary: Summary) -> dict[str, Any]:
    return asdict(summary)
