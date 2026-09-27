"""Offline checks on eval/benchmark result files.

Reads per-item records from JSON or JSONL and looks for the measurement traps
that are visible in the numbers themselves: empty answers at the token cap,
cap-hits scored as wrong, arms truncated at different rates, all-zero arms,
and tool calls scored as wrong answers. Field names vary by harness, so each
record is read through a small set of common aliases; a file whose records
carry none of them is reported as not understood rather than as clean.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

MAX_RESULTS_BYTES = 64 * 1024 * 1024
MAX_RECORDS = 200_000

IMPLEMENTED_TRAPS = frozenset({"12", "16", "36", "37", "42", "64"})

_FINISH = ("finish_reason", "stop_reason", "done_reason")
_CONTENT = ("content", "response", "output", "completion", "answer", "prediction", "generated_text")
_REASONING = ("reasoning_content", "reasoning", "thinking")
_SCORE = ("correct", "is_correct", "score", "acc", "accuracy", "pass", "passed", "exact_match")
_ARM = ("arm", "variant", "condition", "config", "model", "system")
_LIST_KEYS = ("results", "samples", "items", "records", "data", "predictions", "logs")


def _records(path: Path) -> list[dict[str, Any]]:
    if path.stat().st_size > MAX_RESULTS_BYTES:
        raise ValueError(f"results file exceeds {MAX_RESULTS_BYTES} bytes: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        value = json.loads(text)
    except ValueError:
        value = [json.loads(line) for line in text.splitlines() if line.strip().startswith("{")]
    if isinstance(value, dict):
        for key in _LIST_KEYS:
            if isinstance(value.get(key), list):
                value = value[key]
                break
        else:
            value = [value]
    return [item for item in value[:MAX_RECORDS] if isinstance(item, dict)]


def _choice(record: dict[str, Any]) -> dict[str, Any]:
    """Unwrap an OpenAI-shaped envelope when present."""
    for holder in (record, record.get("response") if isinstance(record.get("response"), dict) else None):
        if holder and isinstance(holder.get("choices"), list) and holder["choices"]:
            choice = holder["choices"][0]
            message = choice.get("message") or {}
            return {
                "finish_reason": choice.get("finish_reason"),
                "content": message.get("content"),
                "reasoning_content": message.get("reasoning_content") or message.get("reasoning"),
                "tool_calls": message.get("tool_calls"),
            }
    return {}


def _get(record: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in record:
            return record[name]
    return None


def _normalise(record: dict[str, Any]) -> dict[str, Any]:
    envelope = _choice(record)
    content = envelope.get("content") if envelope else _get(record, _CONTENT)
    if isinstance(content, dict):
        content = _choice(content).get("content")
    score = _get(record, _SCORE)
    if isinstance(score, bool):
        score = float(score)
    elif not isinstance(score, (int, float)):
        score = None
    return {
        "finish": str(envelope.get("finish_reason") or _get(record, _FINISH) or "").lower() or None,
        "content": content,
        "reasoning": envelope.get("reasoning_content") or _get(record, _REASONING),
        "tool_calls": envelope.get("tool_calls") or record.get("tool_calls"),
        "score": score,
        "arm": str(_get(record, _ARM)) if _get(record, _ARM) is not None else None,
    }


def _empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _items(n: int) -> str:
    return f"{n} item" + ("" if n == 1 else "s")


def _finding(trap: str, message: str, evidence: str = "", certainty: str = "possible") -> dict[str, Any]:
    return {"trap_id": trap, "certainty": certainty, "message": message, "evidence": evidence[:300]}


def inspect_results(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if target.is_symlink():
        raise ValueError(f"symlink input is refused: {path}")
    rows = [_normalise(r) for r in _records(target)]
    report: dict[str, Any] = {"kind": "eval_results", "path": str(target), "records": len(rows),
                              "findings": [], "notes": []}
    findings = report["findings"]
    understood = [r for r in rows if r["finish"] or r["score"] is not None or r["content"] is not None]
    if not understood:
        report["notes"].append("no per-item finish_reason, content or score fields recognised; nothing checked")
        return report

    capped = [r for r in understood if r["finish"] in ("length", "max_tokens")]
    empty_capped = [r for r in capped if _empty(r["content"])]
    if len(empty_capped) >= max(1, len(understood) // 50):
        findings.append(_finding(
            "12", f"{len(empty_capped)} of {len(understood)} items stopped at the token cap with empty "
            "content. These score as wrong but are a budget problem; re-run them with a larger max_tokens "
            "before concluding anything about capability."))

    scored = [r for r in understood if r["score"] is not None]
    wrong = [r for r in scored if r["score"] == 0]
    wrong_capped = [r for r in wrong if r["finish"] in ("length", "max_tokens")]
    if wrong and len(wrong_capped) >= max(2, len(wrong) // 5):
        findings.append(_finding(
            "16", f"{len(wrong_capped)} of {len(wrong)} wrong answers hit the token cap. Report truncation "
            "separately; a cap-hit is not the same failure as a wrong answer."))

    null_stop = [r for r in understood if r["finish"] == "stop" and r["content"] is None and not _empty(r["reasoning"])]
    if null_stop:
        findings.append(_finding(
            "64", f"{_items(len(null_stop))} finished with 'stop' and null content while the reasoning field "
            "holds text; the answer was delivered as reasoning and scored as empty."))

    tool_wrong = [r for r in wrong if r["tool_calls"] and _empty(r["content"])]
    if tool_wrong:
        findings.append(_finding(
            "42", f"{_items(len(tool_wrong))} answered with a tool call and were scored wrong; a single-turn "
            "harness counts a tool call as a wrong answer."))

    arms: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in understood:
        if row["arm"] is not None:
            arms[row["arm"]].append(row)
    if len(arms) >= 2:
        rates = {arm: sum(r["finish"] in ("length", "max_tokens") for r in items) / len(items)
                 for arm, items in arms.items() if len(items) >= 10}
        if len(rates) >= 2:
            low, high = min(rates.items(), key=lambda kv: kv[1]), max(rates.items(), key=lambda kv: kv[1])
            if high[1] - low[1] >= 0.05 and high[1] >= 2 * max(low[1], 0.01):
                findings.append(_finding(
                    "36", f"Truncation differs by arm: {high[0]} {high[1]:.0%} vs {low[0]} {low[1]:.0%}. The "
                    "same token cap handicaps the arm that reasons longer; compare arms only at matched "
                    "truncation or report it beside every score."))
    zero_arms = [arm for arm, items in arms.items()
                 if len([r for r in items if r["score"] is not None]) >= 10
                 and all(r["score"] == 0 for r in items if r["score"] is not None)]
    all_scored_zero = len(scored) >= 10 and all(r["score"] == 0 for r in scored)
    if zero_arms or all_scored_zero:
        who = ", ".join(zero_arms) if zero_arms else "every item"
        findings.append(_finding(
            "37", f"Scores are zero for {who}. A uniform zero is usually the harness (parsing, template, "
            "stop sequences, API surface), not the model; hand-read five items before reporting it."))
    return report
