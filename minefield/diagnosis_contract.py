"""Machine-enforced diagnosis semantics for every agent-facing match."""

from __future__ import annotations

import re
from typing import Any, Iterable

DIAGNOSIS_LEVELS = (
    "CONFIRMED_BY_DIRECT_PROBE",
    "STRONG_CONDITION_MATCH_REQUIRES_CONFIRMATION",
    "POSSIBLE_RELATED_TRAP",
    "CONDITION_MISMATCH",
    "NOT_APPLICABLE",
    "NOT_DOCUMENTED",
    "INCONCLUSIVE",
)

CONDITION_FIELDS = (
    "gpu_architecture",
    "device_class",
    "node_count",
    "parallelism",
    "topology",
    "serving_stack",
    "stack_version",
    "model_family",
    "exact_checkpoint",
    "quantization",
    "context_regime",
    "concurrency_regime",
    "failure_stage",
    "operating_system",
)

CRITICAL_FIELDS = frozenset({
    "gpu_architecture", "device_class", "node_count", "parallelism",
    "topology", "serving_stack", "stack_version", "model_family",
    "exact_checkpoint", "quantization",
})

HARDWARE_ARCHITECTURES = {
    "gb10": "blackwell",
    "dgx spark": "blackwell",
    "rtx 5090": "blackwell",
    "5090": "blackwell",
    "rtx 3090": "ampere",
    "3090": "ampere",
    "apple silicon": "apple silicon",
}
REQUIRED_MATCH_FIELDS = frozenset({
    "trap_id", "diagnosis_level", "evidence_status", "matched_conditions",
    "mismatched_conditions", "unknown_conditions", "direct_probe_support",
    "direct_probe_result",
    "mechanism_status", "observed_symptom", "pattern_resemblance",
    "supported_mechanism", "proposed_mechanism", "unresolved_mechanism",
    "confirmation_check", "refutation_check", "conditional_mitigation",
    "remaining_unknowns", "mutation_authority_warning",
})
DEFINITIVE_CAUSAL_RE = re.compile(
    r"\b(?:is caused by|the root cause is|this proves|your gpu has|"
    r"this is definitely trap)\b",
    re.I,
)


def _normal(value: Any) -> str:
    return re.sub(r"[^a-z0-9.+_-]+", " ", str(value).lower()).strip()


def _values(value: Any) -> list[str]:
    if value is None:
        return []
    raw = value if isinstance(value, (list, tuple, set)) else [value]
    return sorted({_normal(item) for item in raw if _normal(item)})


def normalize_conditions(conditions: dict[str, Any] | None) -> dict[str, list[str]]:
    conditions = conditions or {}
    return {field: _values(conditions.get(field)) for field in CONDITION_FIELDS}


def _tokens(pattern: str, text: str) -> list[str]:
    return sorted({_normal(item) for item in re.findall(pattern, text, re.I)})


def _stack_versions(text: str, stacks: list[str]) -> list[str]:
    versions: set[str] = set()
    for stack in stacks:
        escaped = re.escape(stack).replace(r"\ ", r"\s*")
        for match in re.finditer(
            rf"{escaped}[^\n]{{0,32}}?\b(v?\d+\.\d+(?:\.\d+)?|b\d{{3,}})\b",
            text,
            re.I,
        ):
            versions.add(_normal(match.group(1)))
    return sorted(versions)


def documented_conditions(entry: dict[str, Any]) -> dict[str, list[str]]:
    """Extract conservative structured applicability from canonical prose."""
    text = " ".join(str(entry.get(key, "")) for key in (
        "exact_conditions", "affected_versions_builds", "title", "symptom",
    ))
    lower = text.lower()
    hardware = [name for name in HARDWARE_ARCHITECTURES if name in lower]
    architecture = sorted({HARDWARE_ARCHITECTURES[item] for item in hardware})
    node_count: list[str] = []
    if re.search(r"\b(?:single[- ]node|one[- ]node|1[- ]node)\b", lower):
        node_count.append("1")
    if re.search(r"\b(?:two[- ]node|dual[- ]node|2[- ]node)\b", lower):
        node_count.append("2")
    parallelism = []
    if re.search(r"\btp\s*=?\s*\d|\btensor parallel", lower):
        parallelism.append("tp")
    if re.search(r"\bpp\s*=?\s*\d|\bpipeline parallel", lower):
        parallelism.append("pp")
    topology = []
    if node_count:
        topology.extend("single-node" if item == "1" else f"{item}-node" for item in node_count)
    topology.extend(parallelism)
    stacks = [_normal(item) for item in entry.get("affected_stacks", [])]
    models = [_normal(item) for item in entry.get("affected_models", [])]
    model_families = _tokens(
        r"\b(?:qwen(?:\s*3(?:\.\d+)?)?|deepseek|nemotron|minimax|"
        r"ternary[- ]bonsai|laguna|mistral|hy3)\b",
        text,
    )
    checkpoints = _tokens(
        r"\b(?:[\w.-]+/)?(?:qwen|deepseek|nemotron|minimax|ternary[- ]bonsai|"
        r"laguna|mistral|hy3)[\w./+-]{2,}\b",
        text,
    )
    quantization = _tokens(
        r"\b(?:nvfp4|fp8|bf16|fp16|f16|q\d{1,2}(?:_[a-z0-9]+)?|"
        r"int\d+|gguf|awq|gptq)\b",
        text,
    )
    versions = _stack_versions(text, stacks)
    operating_system = [
        name for name in ("linux", "windows", "macos")
        if name in lower
    ]
    return normalize_conditions({
        "gpu_architecture": architecture,
        "device_class": hardware,
        "node_count": node_count,
        "parallelism": parallelism,
        "topology": topology,
        "serving_stack": stacks,
        "stack_version": versions,
        "model_family": model_families,
        "exact_checkpoint": checkpoints + models,
        "quantization": quantization,
        "context_regime": _tokens(r"\b\d+(?:k|,\d{3})\s*(?:context|tokens?)\b", text),
        "concurrency_regime": _tokens(r"\b(?:concurrency|seqs?)\s*=?\s*\d+\b", text),
        "failure_stage": [
            item for item in ("startup", "load", "prefill", "decode", "first request", "sustained")
            if item in lower
        ],
        "operating_system": operating_system,
    })


def _compatible(field: str, user_values: list[str], documented: list[str]) -> bool:
    if field == "gpu_architecture":
        return bool(set(user_values) & set(documented))
    return any(
        left == right or (len(left) >= 4 and left in right) or (len(right) >= 4 and right in left)
        for left in user_values for right in documented
    )


def compare_conditions(
    documented: dict[str, Any] | None,
    observed: dict[str, Any] | None,
) -> tuple[list[str], list[str], list[str]]:
    expected = normalize_conditions(documented)
    actual = normalize_conditions(observed)
    matched: list[str] = []
    mismatched: list[str] = []
    unknown: list[str] = []
    for field in CONDITION_FIELDS:
        wanted = expected[field]
        got = actual[field]
        if wanted and got:
            detail = f"{field}: observed={','.join(got)}; documented={','.join(wanted)}"
            (matched if _compatible(field, got, wanted) else mismatched).append(detail)
        elif wanted:
            unknown.append(f"{field}: user condition not supplied; documented={','.join(wanted)}")
        elif got:
            unknown.append(f"{field}: trap does not document applicability; observed={','.join(got)}")
    return matched, mismatched, unknown


def diagnosis_level(
    *,
    direct_probe_support: bool,
    direct_probe_result: str,
    matched: Iterable[str],
    mismatched: Iterable[str],
    unknown: Iterable[str],
    symptom_score: int,
) -> str:
    mismatched = list(mismatched)
    matched = list(matched)
    unknown = list(unknown)
    critical_mismatch = any(item.split(":", 1)[0] in CRITICAL_FIELDS for item in mismatched)
    if direct_probe_result == "refuted":
        return "NOT_APPLICABLE"
    if direct_probe_support:
        return "CONFIRMED_BY_DIRECT_PROBE"
    if critical_mismatch:
        return "CONDITION_MISMATCH"
    if symptom_score >= 12 and matched and not mismatched and not unknown:
        return "STRONG_CONDITION_MATCH_REQUIRES_CONFIRMATION"
    if symptom_score <= 0:
        return "INCONCLUSIVE"
    return "POSSIBLE_RELATED_TRAP"


def contract_for_match(
    entry: dict[str, Any],
    *,
    observed_symptom: str,
    symptom_score: int,
    observed_conditions: dict[str, Any] | None,
    direct_probe_support: bool = False,
    direct_probe_result: str = "not_supplied",
    mechanism_directly_supported: bool = False,
) -> dict[str, Any]:
    documented = entry.get("applicability") or documented_conditions(entry)
    matched, mismatched, unknown = compare_conditions(documented, observed_conditions)
    level = diagnosis_level(
        direct_probe_support=direct_probe_support,
        direct_probe_result=direct_probe_result,
        matched=matched,
        mismatched=mismatched,
        unknown=unknown,
        symptom_score=symptom_score,
    )
    mechanism_status = (
        "SUPPORTED_BY_DIRECT_PROBE"
        if direct_probe_support and mechanism_directly_supported and not mismatched
        else "PROPOSED_NOT_PROVEN"
    )
    limitations = entry.get("known_limitations") or "The documented evidence does not resolve every user condition."
    result = {
        "trap_id": entry["id"],
        "diagnosis_level": level,
        "evidence_status": entry["status"],
        "documented_conditions": documented,
        "matched_conditions": matched,
        "mismatched_conditions": mismatched,
        "unknown_conditions": unknown,
        "direct_probe_support": bool(direct_probe_support),
        "direct_probe_result": direct_probe_result,
        "mechanism_status": mechanism_status,
        "observed_symptom": observed_symptom,
        "pattern_resemblance": (
            f"The supplied symptom text resembles trap {entry['id']}; resemblance is not confirmation."
        ),
        "supported_mechanism": entry["mechanism"] if mechanism_status == "SUPPORTED_BY_DIRECT_PROBE" else "",
        "proposed_mechanism": entry["mechanism"] if mechanism_status == "PROPOSED_NOT_PROVEN" else "",
        "unresolved_mechanism": "" if mechanism_status == "SUPPORTED_BY_DIRECT_PROBE" else limitations,
        "confirmation_check": entry["check"],
        "refutation_check": (
            "Run the published check on the user's exact conditions with a paired control. "
            "A contrary result refutes only this candidate."
        ),
        "conditional_mitigation": entry["mitigation"],
        "remaining_unknowns": unknown + [limitations],
        "mutation_authority_warning": (
            "Do not mutate configuration, services, or files unless the user separately authorises it."
        ),
    }
    validate_match_contract(result, expected_evidence_status=entry["status"])
    return result


def validate_match_contract(
    result: dict[str, Any],
    *,
    expected_evidence_status: str | None = None,
) -> None:
    missing = sorted(REQUIRED_MATCH_FIELDS - set(result))
    if missing:
        raise ValueError("diagnosis contract missing fields: " + ", ".join(missing))
    if result["diagnosis_level"] not in DIAGNOSIS_LEVELS:
        raise ValueError("invalid diagnosis level")
    if expected_evidence_status is not None and result["evidence_status"] != expected_evidence_status:
        raise ValueError("evidence status was upgraded or changed")
    for field in (
        "matched_conditions", "mismatched_conditions", "unknown_conditions",
        "remaining_unknowns",
    ):
        if not isinstance(result[field], list):
            raise ValueError(f"{field} must be a list")
    if not result["confirmation_check"] or not result["refutation_check"]:
        raise ValueError("every candidate requires confirmation and refutation checks")
    if result["diagnosis_level"] == "CONFIRMED_BY_DIRECT_PROBE" and not result["direct_probe_support"]:
        raise ValueError("confirmation requires direct probe support")
    if result["direct_probe_result"] not in {
        "not_supplied", "candidate_requested", "confirmed", "refuted", "inconclusive",
    }:
        raise ValueError("invalid direct probe result")
    if result["direct_probe_support"] != (result["direct_probe_result"] == "confirmed"):
        raise ValueError("direct probe support requires an explicit confirmed result")
    if result["direct_probe_result"] == "refuted" and result["diagnosis_level"] != "NOT_APPLICABLE":
        raise ValueError("a refuting direct probe must refute the candidate")
    if result["mechanism_status"] == "SUPPORTED_BY_DIRECT_PROBE":
        if not result["direct_probe_support"]:
            raise ValueError("supported mechanism requires direct probe support")
    elif result["supported_mechanism"]:
        raise ValueError("unsupported mechanism must not be presented as supported")
    if (
        DEFINITIVE_CAUSAL_RE.search(result["supported_mechanism"])
        and result["mechanism_status"] != "SUPPORTED_BY_DIRECT_PROBE"
    ):
        raise ValueError("definitive causal language requires direct mechanism evidence")


def miss_contract(symptom: str, observed_conditions: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "diagnosis_level": "NOT_DOCUMENTED",
        "observed_symptom": symptom,
        "matches": [],
        "matched_conditions": [],
        "mismatched_conditions": [],
        "unknown_conditions": [
            f"{field}: {','.join(values)}"
            for field, values in normalize_conditions(observed_conditions).items() if values
        ],
        "direct_probe_support": False,
        "direct_probe_result": "not_supplied",
        "mechanism_status": "NOT_DOCUMENTED",
        "remaining_unknowns": ["A registry miss means not documented, never safe."],
    }
