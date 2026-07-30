"""Compile the canonical Markdown registry into deterministic structured data."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
ENTRY_RE = re.compile(r"^(?P<id>\d{2,})-.+\.md$")
TITLE_RE = re.compile(r"^#\s+Trap\s+(\d+):\s*(.+?)\s*$", re.M | re.I)
STATUS_RE = re.compile(r"^\*\*Status:\s*(.+?)(?:\*\*|$)", re.M | re.I)
FINDER_RE = re.compile(
    r"^\*\*Found (?:by|and measured by|and reported by)\s+(.+?)(?:\.\*\*|\*\*|$)",
    re.M | re.I,
)
LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)]+)\)")
RELATED_RE = re.compile(r"(?:trap\s+|\[)(\d{1,3})(?:\]|\b)", re.I)
STACK_NAMES = (
    "vLLM", "llama.cpp", "Ollama", "mlx_lm", "SGLang", "TensorRT-LLM",
    "text-generation-inference", "TabbyAPI", "ExLlama", "LM Studio",
    "text-generation-webui", "transformers", "Docker", "systemd",
)
MODEL_RE = re.compile(
    r"\b(?:Qwen|DeepSeek|Nemotron|MiniMax|Ternary-Bonsai|Laguna|Mistral|Hy3)"
    r"[\w .+/-]{0,70}",
    re.I,
)
STATUS_STEMS = (
    "reproduced here",
    "contributor-measured, conditions as reported",
    "reported by others",
    "measured here, raw not published",
    "under test",
)


class RegistryError(ValueError):
    """The canonical source or its reviewed overrides violate the contract."""


def canonical_paths(root: Path = ROOT) -> list[Path]:
    """Use the repository's actual enumeration: traps/category/NN-*.md."""
    traps = root / "traps"
    paths = [
        path for category in sorted(traps.iterdir()) if category.is_dir()
        for path in sorted(category.iterdir())
        if path.is_file() and ENTRY_RE.match(path.name)
    ]
    ids = [ENTRY_RE.match(path.name).group("id") for path in paths]  # type: ignore[union-attr]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        raise RegistryError(f"duplicate canonical trap IDs: {', '.join(duplicates)}")
    return sorted(paths, key=lambda path: int(ENTRY_RE.match(path.name).group("id")))  # type: ignore[union-attr]


def _readme_symptoms(root: Path) -> dict[str, str]:
    symptoms: dict[str, str] = {}
    for line in (root / "README.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        match = re.search(r"\[(\d{2,})[^\]]*\]\(traps/", cells[2])
        if match:
            symptoms.setdefault(match.group(1), cells[0])
    return symptoms


def _doctor_paths(root: Path) -> dict[str, str]:
    source = (root / "doctor" / "minefield_doctor.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "TRAP_PATHS" for t in node.targets):
                value = ast.literal_eval(node.value)
                return {str(key): str(path) for key, path in value.items()}
    raise RegistryError("doctor TRAP_PATHS was not found")


def _clean(text: str, limit: int = 2400) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[`*_#]", "", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _section(text: str, labels: Iterable[str], fallback: str = "") -> str:
    alternatives = "|".join(re.escape(label) for label in labels)
    patterns = (
        rf"^\*\*(?:{alternatives})[.:]?\*\*\s*(.*?)(?=^\*\*[^*]+\*\*|^##?\s|\Z)",
        rf"^##\s+(?:{alternatives})[^\n]*\n(.*?)(?=^##?\s|\Z)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.M | re.S | re.I)
        if match:
            value = _clean(match.group(1))
            if value:
                return value
    return _clean(fallback)


def _status_labels(raw: str) -> list[str]:
    lower = raw.lower()
    if re.search(r"\b(?:universally proven|verified everywhere|guaranteed|conclusive)\b", lower):
        raise RegistryError(f"evidence status contains a prohibited upgrade: {raw!r}")
    labels = [status for status in STATUS_STEMS if status in lower]
    if not labels:
        raise RegistryError(f"invalid evidence status: {raw!r}")
    return labels


def _load_overrides(root: Path) -> dict[str, dict[str, Any]]:
    path = root / "registry" / "overrides.json"
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RegistryError(f"malformed overrides: {exc}") from exc
    if not isinstance(value, dict) or any(not isinstance(v, dict) for v in value.values()):
        raise RegistryError("overrides must be an object of trap-id objects")
    protected = {"id", "source_path", "category", "status", "evidence_strength",
                 "doctor_coverage"}
    for trap_id, override in value.items():
        forbidden = sorted(protected & set(override))
        if forbidden:
            raise RegistryError(
                f"override {trap_id} may not replace identity/evidence fields: "
                + ", ".join(forbidden)
            )
    return value


def compile_registry(root: Path = ROOT) -> dict[str, Any]:
    paths = canonical_paths(root)
    symptoms = _readme_symptoms(root)
    doctor = _doctor_paths(root)
    overrides = _load_overrides(root)
    canonical_ids = {ENTRY_RE.match(path.name).group("id") for path in paths}  # type: ignore[union-attr]
    unknown_overrides = sorted(set(overrides) - canonical_ids)
    if unknown_overrides:
        raise RegistryError(f"overrides name noncanonical IDs: {', '.join(unknown_overrides)}")

    entries: list[dict[str, Any]] = []
    for path in paths:
        trap_id = ENTRY_RE.match(path.name).group("id")  # type: ignore[union-attr]
        text = path.read_text(encoding="utf-8")
        title_match = TITLE_RE.search(text)
        status_match = STATUS_RE.search(text)
        finder_match = FINDER_RE.search(text)
        if not title_match or title_match.group(1).zfill(2) != trap_id:
            raise RegistryError(f"{path}: missing or mismatched trap title")
        if not status_match:
            raise RegistryError(f"{path}: missing status")
        if not finder_match:
            raise RegistryError(f"{path}: missing contributor attribution")
        status_raw = _clean(status_match.group(1), 800)
        symptom = _section(text, ("Symptom", "What you see"), symptoms.get(trap_id, ""))
        mechanism = _section(
            text,
            ("Mechanism", "Cause", "What actually governs it", "Why this is recorded", "The trap"),
            text[status_match.end():status_match.end() + 1800],
        )
        check = _section(
            text,
            (
                "The check", "Check", "Check it", "The check that catches it",
                "The check for all three", "The detection fingerprint",
                "The check, and one warning about how you check",
                "The check a stranger can run", "Check it in one request",
                "Check it in two requests", "What actually detects it",
            ),
            "",
        )
        mitigation = _section(text, ("The fix", "Fix", "Mitigation", "Workaround"), check)
        if not symptom or not check:
            raise RegistryError(f"{path}: compiler could not resolve symptom/check")

        stacks_text = _section(text, ("Stacks and builds bitten", "Scope"), "")
        entry: dict[str, Any] = {
            "id": trap_id,
            "title": _clean(title_match.group(2), 500),
            "category": path.parent.name,
            "source_path": path.relative_to(root).as_posix(),
            "symptom": symptom,
            "mechanism": mechanism,
            "check": check,
            "mitigation": mitigation,
            "status": status_raw,
            "evidence_strength": _status_labels(status_raw),
            "contributor": _clean(finder_match.group(1), 500) if finder_match else "unknown",
            "affected_stacks": [name for name in STACK_NAMES if re.search(re.escape(name), text, re.I)],
            "affected_models": sorted({
                _clean(match.group(0), 100).rstrip(" .,:;-")
                for match in MODEL_RE.finditer(stacks_text or text[:5000])
            }),
            "affected_versions_builds": stacks_text,
            "exact_conditions": stacks_text,
            "public_evidence_links": sorted(set(LINK_RE.findall(text))),
            "doctor_coverage": {
                "implemented": trap_id in doctor,
                "source": f"doctor/{doctor[trap_id]}" if trap_id in doctor else None,
            },
            "diagnostic_modalities": [],
            "known_limitations": _section(
                text, ("Limitations", "What this does and does not say", "Scope"), ""
            ),
            "related_traps": sorted(
                {item.zfill(2) for item in RELATED_RE.findall(text)}
                - {trap_id},
                key=int,
            ),
            "supersession": None,
        }
        entry.update(overrides.get(trap_id, {}))
        if Path(entry["source_path"]).is_absolute() or not (root / entry["source_path"]).is_file():
            raise RegistryError(f"{path}: generated source_path is not canonical")
        entries.append(entry)

    payload = {
        "schema_version": "1.0",
        "canonical_enumeration": "traps/<category>/NN-*.md",
        "canonical_trap_count": len(entries),
        "doctor_implemented_trap_count": len(doctor),
        "entries": entries,
    }
    payload["content_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload


def dumps(payload: Any, *, compact: bool = False) -> str:
    kwargs = {"sort_keys": True, "ensure_ascii": False}
    if compact:
        return json.dumps(payload, separators=(",", ":"), **kwargs) + "\n"
    return json.dumps(payload, indent=2, **kwargs) + "\n"


def load_registry(root: Path = ROOT) -> dict[str, Any]:
    generated = root / "dist" / "MINEFIELD_REGISTRY.json"
    if generated.exists():
        return json.loads(generated.read_text(encoding="utf-8"))
    embedded = Path(__file__).resolve().parent / "data" / "MINEFIELD_REGISTRY.json"
    if embedded.exists():
        return json.loads(embedded.read_text(encoding="utf-8"))
    return compile_registry(root)
