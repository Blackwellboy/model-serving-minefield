#!/usr/bin/env python3
"""Classify captured renders without contacting models or endpoints."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from minefield.inline_system import classify_manifest  # noqa: E402


MARKERS = {
    "zai-org/GLM-5.1": [
        {"role": "system", "open": "<|system|>"},
        {"role": "user", "open": "<|user|>"},
        {"role": "assistant", "open": "<|assistant|>"},
        {"role": "tool", "open": "<|observation|>"},
    ],
    "zai-org/GLM-5.2": [
        {"role": "system", "open": "<|system|>"},
        {"role": "user", "open": "<|user|>"},
        {"role": "assistant", "open": "<|assistant|>"},
        {"role": "tool", "open": "<|observation|>"},
    ],
    "moonshotai/Kimi-K2.6": [
        {
            "role": "system",
            "open": "<|im_system|>system<|im_middle|>",
            "close": "<|im_end|>",
        },
        {
            "role": "user",
            "open": "<|im_user|>user<|im_middle|>",
            "close": "<|im_end|>",
        },
        {
            "role": "assistant",
            "open": "<|im_assistant|>assistant<|im_middle|>",
            "close": "<|im_end|>",
        },
        {
            "role": "tool",
            "open": "<|im_system|>tool<|im_middle|>",
            "close": "<|im_end|>",
        },
    ],
    "moonshotai/Kimi-K3": [
        {
            "role": "system",
            "open": '<|open|>message role="system"<|sep|>',
            "close": "<|close|>message",
        },
        {
            "role": "user",
            "open": '<|open|>message role="user"<|sep|>',
            "close": "<|close|>message",
        },
        {
            "role": "assistant",
            "open": '<|open|>message role="assistant"<|sep|>',
            "close": "<|close|>message",
        },
        {
            "role": "tool",
            "open": '<|open|>message role="tool"<|sep|>',
            "close": "<|close|>message",
        },
    ],
}


def rendered(item: dict[str, Any], name: str) -> dict[str, Any]:
    record = item["executed_renders"][name]
    if record["status"] == "EXECUTED":
        result = {"rendered_text": record["rendered_text"]}
        if "decoded_from_token_ids" in record:
            result["decoded_from_token_ids"] = record["decoded_from_token_ids"]
        return result
    return {
        "rejected": True,
        "error": record.get("error"),
    }


def classify(
    model: str,
    item: dict[str, Any],
    primary_name: str,
    no_system_name: str,
) -> dict[str, Any]:
    primary = rendered(item, primary_name)
    primary["messages"] = [
        {"role": message["role"], "content": message.get("content", "")}
        for message in RAW["probes"][primary_name]
    ]
    manifest = {
        "schema_version": "1.0",
        "evidence_surface": item["evidence_surface"],
        "model": model,
        "revision": item["revision"],
        "target_texts": ["LATESYS"],
        "leading_system_text": "S",
        "markers": MARKERS.get(model, []),
        "primary": primary,
        "controls": {
            "no_system": rendered(item, no_system_name),
            "leading_system": rendered(item, "control_leading_system"),
        },
    }
    result = classify_manifest(manifest)
    return {"manifest": manifest, "result": result}


def deepseek_runtime_record() -> dict[str, Any]:
    manifest = {
        "schema_version": "1.0",
        "evidence_surface": "ENDPOINT_RENDER_REPRODUCED",
        "model": "DeepSeek-V4-Flash lane documented by Trap 56",
        "revision_context": (
            "Existing public Trap 56 live /tokenize finding. Pinned upstream "
            "source corroboration is recorded separately."
        ),
        "target_texts": ["LATESYS"],
        "leading_system_text": "S",
        "markers": [
            {"role": "user", "open": "<|User|>"},
            {"role": "assistant", "open": "<|Assistant|>"},
        ],
        "primary": {
            "rendered_text": (
                "<BOS><|User|>QLATESYS<|User|>Q2"
                "<|Assistant|></think>"
            ),
            "messages": RAW["probes"]["primary_inline_system"],
        },
        "controls": {
            "no_system": {
                "rendered_text": (
                    "<BOS><|User|>Q<|User|>Q2<|Assistant|></think>"
                )
            },
            "leading_system": {
                "rendered_text": (
                    "<BOS>S<|User|>Q<|Assistant|></think>"
                )
            },
        },
    }
    return {"manifest": manifest, "result": classify_manifest(manifest)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    global RAW
    RAW = json.loads(Path(args.input).read_text(encoding="utf-8"))
    matrix: dict[str, Any] = {
        "schema_version": "1.0",
        "_detect_secrets_review": (
            "pragma: allowlist secret - public immutable revisions and file "
            "digests, not credentials"
        ),
        "source_manifest_sha256": __import__("hashlib").sha256(
            Path(args.input).read_bytes()
        ).hexdigest(),
        "records": {
            "deepseek_existing_runtime": deepseek_runtime_record(),
        },
    }
    for model, item in RAW["models"].items():
        if "executed_renders" not in item:
            continue
        matrix["records"][f"{model}:primary"] = classify(
            model, item, "primary_inline_system", "control_no_system"
        )
        matrix["records"][f"{model}:tool_boundary"] = classify(
            model, item, "tool_boundary_inline_system", "tool_boundary_no_system"
        )
    output = Path(args.output)
    output.write_text(
        json.dumps(
            matrix, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ) + "\n",
        encoding="utf-8",
    )
    return 0


RAW: dict[str, Any]

if __name__ == "__main__":
    raise SystemExit(main())
