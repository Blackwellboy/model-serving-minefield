"""Validate explicit Doctor operator inputs before any endpoint is contacted."""
from __future__ import annotations

import re
from typing import Any


def validate_request_budget(value: int | None) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
        raise ValueError("max_requests must be a nonnegative integer")


def validate_operator_inputs(*, hf_revision: str = "main", server_max_tokens: int | None = None,
                             benchmark_target_tokens: int | None = None,
                             benchmark_prompt_text: str | None = None,
                             thinking_budget_marker_ids: str | None = None) -> dict[str, Any]:
    if not isinstance(hf_revision, str) or not hf_revision.strip() or len(hf_revision) > 200:
        raise ValueError("hf_revision must be a nonempty revision of at most 200 characters")
    for name, value, upper in (("server_max_tokens", server_max_tokens, 255),
                               ("benchmark_target_tokens", benchmark_target_tokens, 2**31 - 1)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)
                                  or not 1 <= value <= upper):
            raise ValueError(f"{name} must be an integer in 1..{upper}")
    if (benchmark_target_tokens is None) != (benchmark_prompt_text is None):
        raise ValueError("benchmark_target_tokens and benchmark_prompt_text must be supplied together")
    if benchmark_prompt_text is not None and (not isinstance(benchmark_prompt_text, str)
                                               or not benchmark_prompt_text.strip()
                                               or len(benchmark_prompt_text) > 8192):
        raise ValueError("benchmark_prompt_text must contain 1..8192 characters")
    if thinking_budget_marker_ids is not None:
        if not isinstance(thinking_budget_marker_ids, str) or not re.fullmatch(
                r"\s*\d{1,10}\s*,\s*\d{1,10}\s*", thinking_budget_marker_ids):
            raise ValueError("thinking_budget_marker_ids must be START,END nonnegative integers")
        if any(int(value.strip()) > 2**31 - 1 for value in thinking_budget_marker_ids.split(",")):
            raise ValueError("thinking_budget_marker_ids exceed the supported integer range")
    return dict(hf_revision=hf_revision, server_max_tokens=server_max_tokens,
                benchmark_target_tokens=benchmark_target_tokens,
                benchmark_prompt_text=benchmark_prompt_text,
                thinking_budget_marker_ids=thinking_budget_marker_ids)
