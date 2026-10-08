"""High-specificity diagnostic fingerprints used only for candidate routing.

Fingerprints are exact identifiers/error shapes, not prose synonyms. A match is
strong evidence for which canonical entry to read, but remains a lead: it never
confirms the trap's mechanism or authorises a mitigation by itself.
"""

from __future__ import annotations

import re
from typing import NamedTuple


class Fingerprint(NamedTuple):
    trap_id: str
    pattern: str
    reason: str


# First batch is intentionally tiny and benchmark-grounded: these are the four
# real pasted report lines in benchmarks/symptom_queries.json that previously
# had no contextual log signature at all.
FINGERPRINTS = (
    Fingerprint(
        "77",
        r"Unknown\s+vLLM\s+environment\s+variable\s+detected\s*:",
        "exact vLLM unknown-environment-variable diagnostic",
    ),
    Fingerprint(
        "118",
        r"shm_broadcast\.py:705[^\n]{0,240}No\s+available\s+shared\s+memory\s+broadcast\s+block",
        "Ray/vLLM shm_broadcast timeout line from the silent-boot failure shape",
    ),
    Fingerprint(
        "119",
        r"max_total_tokens\s*=\s*\d+\s+is\s+larger\s+than\s+the\s+profiled\s+value\s+\d+",
        "resolved max_total_tokens exceeds the runtime-profiled capacity",
    ),
    Fingerprint(
        "19",
        r"auto\s+tool\s+choice\s+requires\s+--enable-auto-tool-choice\s+and\s+--tool-call-parser",
        "explicit auto-tool-choice parser/configuration requirement",
    ),
    Fingerprint(
        "125",
        r"\bMemoryMax\s*=",
        "systemd/cgroup MemoryMax is present as a serving-memory guard",
    ),
    Fingerprint(
        "143",
        r"\bsliding_window\b[\s\S]{0,320}\bmax_window_layers\b|\bmax_window_layers\b[\s\S]{0,320}\bsliding_window\b",
        "Qwen sliding-window configuration keys appear together",
    ),
    Fingerprint(
        "100",
        r"\bhipErrorInvalidImage\b",
        "exact ROCm/HIP invalid-code-object diagnostic",
    ),
    Fingerprint(
        "130",
        r"\bcudagraph_capture_sizes\b",
        "effective CUDA-graph capture-size list identifier",
    ),
)


def fingerprints_in_text(text: str) -> dict[str, str]:
    """Return trap id -> human-readable reason for concrete fingerprint hits."""
    joined = " ".join((text or "").splitlines())
    hits: dict[str, str] = {}
    for fp in FINGERPRINTS:
        if re.search(fp.pattern, joined, re.I | re.M):
            hits.setdefault(fp.trap_id, fp.reason)
    return hits
