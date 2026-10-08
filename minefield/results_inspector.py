"""Offline checks on eval/benchmark result files.

Reads bounded per-item records from JSON or JSONL and looks for measurement
traps visible in the numbers themselves: empty answers at the token cap,
cap-hits scored as wrong, arms truncated at different rates, all-zero arms,
and tool calls scored as wrong answers. Field names vary by harness, so each
record is read through common aliases; a file whose records carry none of them
is reported as not understood rather than as clean.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

MAX_RESULTS_BYTES = 64 * 1024 * 1024
MAX_RECORDS = 200_000

IMPLEMENTED_TRAPS = frozenset({"12", "16", "36", "37", "42", "64", "137", "149", "155", "156", "158"})

_FINISH = ("finish_reason", "stop_reason", "done_reason")
_CONTENT = ("content", "response", "output", "completion", "answer", "prediction", "generated_text")
_REASONING = ("reasoning_content", "reasoning", "thinking")
_SCORE = ("correct", "is_correct", "score", "acc", "accuracy", "pass", "passed", "exact_match")
_ARM = ("arm", "variant", "condition", "config", "model", "system")
_LIST_KEYS = ("results", "samples", "items", "records", "data", "predictions", "logs")


def _records(path: Path) -> list[dict[str, Any]]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ValueError(f"results file is not readable: {path}") from exc
    if size > MAX_RESULTS_BYTES:
        raise ValueError(f"results file exceeds {MAX_RESULTS_BYTES} bytes: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"results file is not valid readable UTF-8: {path}") from exc
    if not text.strip():
        raise ValueError(f"results file is empty: {path}")

    try:
        value: Any = json.loads(text)
    except json.JSONDecodeError:
        records: list[dict[str, Any]] = []
        saw_line = False
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            saw_line = True
            if len(records) >= MAX_RECORDS:
                break
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {number}: {exc.msg}") from exc
            if isinstance(item, dict):
                records.append(item)
        if not saw_line:
            raise ValueError(f"results file has no JSON records: {path}")
        return records

    if isinstance(value, dict):
        for key in _LIST_KEYS:
            candidate = value.get(key)
            if isinstance(candidate, list):
                value = candidate
                break
        else:
            value = [value]
    elif not isinstance(value, list):
        raise ValueError(
            f"results JSON must be an object, an array of objects, or JSONL objects: {path}"
        )
    return [item for item in value[:MAX_RECORDS] if isinstance(item, dict)]


def _choice(record: dict[str, Any]) -> dict[str, Any]:
    """Unwrap an OpenAI-shaped envelope when it has the expected object shape."""
    nested = record.get("response")
    holders = (record, nested if isinstance(nested, dict) else None)
    for holder in holders:
        if not isinstance(holder, dict):
            continue
        choices = holder.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            continue
        choice = choices[0]
        raw_message = choice.get("message")
        message = raw_message if isinstance(raw_message, dict) else {}
        return {
            "finish_reason": choice.get("finish_reason"),
            "content": message.get("content") if message else choice.get("text"),
            "reasoning_content": message.get("reasoning_content") or message.get("reasoning"),
            "tool_calls": message.get("tool_calls"),
        }
    return {}


def _get(record: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in record:
            return record[name]
    return None


def _short_scalar(value: Any, limit: int = 200) -> str | None:
    if isinstance(value, str):
        return value[:limit]
    if isinstance(value, (int, float, bool)) and not isinstance(value, complex):
        return str(value)[:limit]
    return None


def _request_object(record: dict[str, Any]) -> dict[str, Any]:
    for key in ("request", "input", "payload", "body"):
        value = record.get(key)
        if isinstance(value, dict):
            return value
    return record


def _reasoning_tokens(record: dict[str, Any]) -> int | None:
    holders = [record]
    nested = record.get("response")
    if isinstance(nested, dict):
        holders.append(nested)
    for holder in holders:
        direct = holder.get("reasoning_tokens")
        if isinstance(direct, int) and not isinstance(direct, bool):
            return direct
        usage = holder.get("usage")
        if not isinstance(usage, dict):
            continue
        direct = usage.get("reasoning_tokens")
        if isinstance(direct, int) and not isinstance(direct, bool):
            return direct
        details = usage.get("completion_tokens_details")
        if isinstance(details, dict):
            value = details.get("reasoning_tokens")
            if isinstance(value, int) and not isinstance(value, bool):
                return value
    return None


def _thinking_off(record: dict[str, Any]) -> bool:
    req = _request_object(record)
    if req.get("enable_thinking") is False or req.get("think") is False:
        return True
    if str(req.get("reasoning_effort") or "").lower() in {"none", "off"}:
        return True
    kwargs = req.get("chat_template_kwargs")
    return isinstance(kwargs, dict) and kwargs.get("enable_thinking") is False


def _tool_history(record: dict[str, Any]) -> bool:
    req = _request_object(record)
    messages = req.get("messages")
    if not isinstance(messages, list):
        return False
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("role") == "tool" or message.get("tool_calls"):
            return True
    return False


def _usage_value(record: dict[str, Any], key: str) -> int | None:
    holders = [record]
    nested = record.get("response")
    if isinstance(nested, dict):
        holders.append(nested)
    for holder in holders:
        usage = holder.get("usage")
        if isinstance(usage, dict) and isinstance(usage.get(key), int):
            return usage[key]
        if isinstance(holder.get(key), int):
            return holder[key]
    return None


def _request_max_tokens(record: dict[str, Any]) -> int | None:
    req = _request_object(record)
    for key in ("max_tokens", "max_completion_tokens"):
        if isinstance(req.get(key), int):
            return req[key]
    return None


def _structured_json_request(record: dict[str, Any]) -> bool:
    req = _request_object(record)
    rf = req.get("response_format")
    if not isinstance(rf, dict):
        return False
    return rf.get("type") in {"json_schema", "json_object"}


def _thinking_on(record: dict[str, Any]) -> bool:
    req = _request_object(record)
    if req.get("enable_thinking") is True or req.get("think") is True:
        return True
    effort = str(req.get("reasoning_effort") or "").lower()
    if effort and effort not in {"none", "off"}:
        return True
    kwargs = req.get("chat_template_kwargs")
    return isinstance(kwargs, dict) and kwargs.get("enable_thinking") is True


def _valid_json_text(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        json.loads(value)
        return True
    except Exception:
        return False


def _normalise(record: dict[str, Any]) -> dict[str, Any]:
    envelope = _choice(record)
    content = envelope.get("content") if envelope else _get(record, _CONTENT)
    if isinstance(content, dict):
        content = _choice(content).get("content")
    score = _get(record, _SCORE)
    if isinstance(score, bool):
        score = float(score)
    elif isinstance(score, (int, float)) and not isinstance(score, bool):
        score = float(score) if math.isfinite(float(score)) else None
    else:
        score = None
    finish_value = envelope.get("finish_reason") or _get(record, _FINISH)
    finish = _short_scalar(finish_value)
    arm_value = _get(record, _ARM)
    return {
        "finish": finish.lower() if finish else None,
        "content": content,
        "reasoning": envelope.get("reasoning_content") or _get(record, _REASONING),
        "tool_calls": envelope.get("tool_calls") or record.get("tool_calls"),
        "score": score,
        "arm": _short_scalar(arm_value),
        "reasoning_tokens": _reasoning_tokens(record),
        "thinking_off": _thinking_off(record),
        "tool_history": _tool_history(record),
        "completion_tokens": _usage_value(record, "completion_tokens"),
        "prompt_tokens": _usage_value(record, "prompt_tokens"),
        "cached_tokens": _usage_value(record, "cached_tokens"),
        "max_tokens": _request_max_tokens(record),
        "structured_json": _structured_json_request(record),
        "thinking_on": _thinking_on(record),
        "selector_rc": record.get("rc", record.get("return_code")),
        "reference_ok": record.get("reference_ok", record.get("allclose")),
        "conversation_id": _short_scalar(record.get("conversation_id") or record.get("session_id")),
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
    rows = [_normalise(record) for record in _records(target)]
    report: dict[str, Any] = {
        "kind": "eval_results",
        "path": str(target),
        "records": len(rows),
        "findings": [],
        "notes": [],
    }
    findings = report["findings"]
    understood = [
        row for row in rows
        if row["finish"] or row["score"] is not None or row["content"] is not None
    ]
    if not understood:
        report["notes"].append(
            "no per-item finish_reason, content or score fields recognised; nothing checked"
        )
        return report

    capped = [row for row in understood if row["finish"] in ("length", "max_tokens")]
    empty_capped = [row for row in capped if _empty(row["content"])]
    if len(empty_capped) >= max(1, len(understood) // 50):
        findings.append(_finding(
            "12", f"{len(empty_capped)} of {len(understood)} items stopped at the token cap with empty "
            "content. These score as wrong but are a budget problem; re-run them with a larger max_tokens "
            "before concluding anything about capability."))

    scored = [row for row in understood if row["score"] is not None]
    wrong = [row for row in scored if row["score"] == 0]
    wrong_capped = [row for row in wrong if row["finish"] in ("length", "max_tokens")]
    if wrong and len(wrong_capped) >= max(2, len(wrong) // 5):
        findings.append(_finding(
            "16", f"{len(wrong_capped)} of {len(wrong)} wrong answers hit the token cap. Report truncation "
            "separately; a cap-hit is not the same failure as a wrong answer."))

    null_stop = [
        row for row in understood
        if row["finish"] == "stop" and row["content"] is None and not _empty(row["reasoning"])
    ]
    if null_stop:
        findings.append(_finding(
            "64", f"{_items(len(null_stop))} finished with 'stop' and null content while the reasoning field "
            "holds text; the answer was delivered as reasoning and scored as empty."))

    tool_wrong = [row for row in wrong if row["tool_calls"] and _empty(row["content"])]
    if tool_wrong:
        findings.append(_finding(
            "42", f"{_items(len(tool_wrong))} answered with a tool call and were scored wrong; a single-turn "
            "harness counts a tool call as a wrong answer."))

    empty_marker_rows = [
        row for row in understood
        if row["thinking_off"] and row["tool_history"]
        and row["reasoning_tokens"] == 2 and _empty(row["reasoning"])
    ]
    if empty_marker_rows:
        findings.append(_finding(
            "158", f"{_items(len(empty_marker_rows))} explicitly disabled thinking after tool history, returned "
            "empty reasoning text, but usage still reports exactly 2 reasoning tokens. That is the empty "
            "thought-marker signature; do not fail thinking-off solely on reasoning_tokens == 0."))

    selector_rows = [
        row for row in understood
        if isinstance(row["selector_rc"], int) and row["selector_rc"] != 0
        and row["reference_ok"] is True
    ]
    if selector_rows:
        findings.append(_finding(
            "137", f"{_items(len(selector_rows))} carry a nonzero rc/return_code while an independent "
            "reference check says the output is correct. Do not interpret the integer as a process failure "
            "until the pinned extension contract says it is an error code."))

    structured_runaway = [
        row for row in understood
        if row["structured_json"] and row["thinking_on"]
        and row["finish"] in ("length", "max_tokens")
        and isinstance(row["content"], str) and row["content"].lstrip().startswith("{")
        and not _valid_json_text(row["content"])
    ]
    if structured_runaway:
        findings.append(_finding(
            "149", f"{_items(len(structured_runaway))} requested structured JSON with thinking enabled, "
            "hit the token cap, opened JSON, and returned invalid/unclosed JSON. Re-run the same schema "
            "thinking-off before certifying the structured-output lane."))

    undercount_rows = [
        row for row in understood
        if row["finish"] in ("length", "max_tokens")
        and isinstance(row["completion_tokens"], int)
        and isinstance(row["max_tokens"], int) and row["max_tokens"] >= 128
        and row["completion_tokens"] < int(row["max_tokens"] * 0.75)
    ]
    if undercount_rows:
        findings.append(_finding(
            "156", f"{_items(len(undercount_rows))} stopped for length while reported completion_tokens "
            "were under 75% of the explicit token cap. That is inconsistent enough to retokenize returned "
            "text before trusting usage or derived tok/s."))

    conversations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in understood:
        if row["conversation_id"] and isinstance(row["cached_tokens"], int) and isinstance(row["prompt_tokens"], int):
            conversations[row["conversation_id"]].append(row)
    thrash = []
    for cid, items in conversations.items():
        if len(items) < 3:
            continue
        cached = [row["cached_tokens"] for row in items]
        prompts = [row["prompt_tokens"] for row in items]
        if min(cached) > 0 and len(set(cached)) == 1 and max(prompts) - min(prompts) >= 128:
            thrash.append((cid, cached[0], min(prompts), max(prompts)))
    if thrash:
        findings.append(_finding(
            "155", f"{len(thrash)} conversation(s) show cached_tokens pinned to one constant while prompt "
            "length grows materially; inspect prefix-slot residency/victim selection rather than attributing "
            "the repeated prefill to model speed.", evidence=str(thrash[:5])))

    arms: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in understood:
        if row["arm"] is not None:
            arms[row["arm"]].append(row)
    if len(arms) >= 2:
        rates = {
            arm: sum(row["finish"] in ("length", "max_tokens") for row in items) / len(items)
            for arm, items in arms.items() if len(items) >= 10
        }
        if len(rates) >= 2:
            low = min(rates.items(), key=lambda item: item[1])
            high = max(rates.items(), key=lambda item: item[1])
            if high[1] - low[1] >= 0.05 and high[1] >= 2 * max(low[1], 0.01):
                findings.append(_finding(
                    "36", f"Truncation differs by arm: {high[0]} {high[1]:.0%} vs {low[0]} {low[1]:.0%}. The "
                    "same token cap handicaps the arm that reasons longer; compare arms only at matched "
                    "truncation or report it beside every score."))
    zero_arms = [
        arm for arm, items in arms.items()
        if len([row for row in items if row["score"] is not None]) >= 10
        and all(row["score"] == 0 for row in items if row["score"] is not None)
    ]
    all_scored_zero = len(scored) >= 10 and all(row["score"] == 0 for row in scored)
    if zero_arms or all_scored_zero:
        who = ", ".join(zero_arms) if zero_arms else "every item"
        findings.append(_finding(
            "37", f"Scores are zero for {who}. A uniform zero is usually the harness (parsing, template, "
            "stop sequences, API surface), not the model; hand-read five items before reporting it."))
    return report
