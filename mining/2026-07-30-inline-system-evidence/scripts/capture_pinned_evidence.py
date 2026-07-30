#!/usr/bin/env python3
"""Capture immutable source hashes and executed inline-system renders.

Jinja sources are rendered directly without model code. Kimi-K3 remote
tokenizer code is the one explicit exception and requires --execute-kimi-k3.
Run it only in the disposable environment documented beside the output.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import traceback
import urllib.request
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer
from transformers.utils.chat_template_utils import render_jinja_template

VLLM_REVISION = "48a077e4cfaa5425ac5df67ce95f07a99c6d26d5"  # pragma: allowlist secret
KIMI_SUPPORT_REVISION = "f5a7cce9b6a61f4d995629a7418c7ea822e34a64"  # pragma: allowlist secret

MODELS = {
    "deepseek-ai/DeepSeek-V4-Flash": {
        "revision": "60d8d70770c6776ff598c94bb586a859a38244f1",  # pragma: allowlist secret
        "type": "Python encoder",
        "files": ["encoding/encoding_dsv4.py", "tokenizer_config.json"],
        "loading_path": (
            "Not AutoTokenizer-discoverable: no auto_map or chat_template. "
            "vLLM uses its maintained DeepseekV4Tokenizer encoder copy."
        ),
    },
    "zai-org/GLM-5.1": {
        "revision": "26e1bd6e011feb778d25ae34b09b07074139d92d",  # pragma: allowlist secret
        "type": "Jinja",
        "files": ["chat_template.jinja", "tokenizer_config.json"],
        "loading_path": "Pinned chat_template.jinja rendered by the standard template path.",
    },
    "zai-org/GLM-5.2": {
        "revision": "b4734de4facf877f85769a911abafc5283eab3d9",  # pragma: allowlist secret
        "type": "Jinja",
        "files": ["chat_template.jinja", "tokenizer_config.json"],
        "loading_path": "Pinned chat_template.jinja rendered by the standard template path.",
    },
    "moonshotai/Kimi-K2.6": {
        "revision": "7eb5002f6aadc958aed6a9177b7ed26bb94011bb",  # pragma: allowlist secret
        "type": "Jinja",
        "files": ["chat_template.jinja", "tokenizer_config.json"],
        "loading_path": "Pinned chat_template.jinja rendered by the standard template path.",
    },
    "moonshotai/Kimi-K3": {
        "revision": "9f62e4e9fffbd0a83ddd60e1c209d828994b3569",  # pragma: allowlist secret
        "type": "upstream remote tokenizer",
        "files": [
            "encoding_k3.py",
            "tokenization_kimi.py",
            "tokenizer_config.json",
            "tiktoken.model",
        ],
        "loading_path": (
            "Pinned AutoTokenizer auto_map with trust_remote_code=True; "
            "vLLM KimiK3Renderer delegates to apply_chat_template."
        ),
    },
    "MiniMaxAI/MiniMax-M2.5": {
        "revision": "f710177d938eff80b684d42c5aa84b382612f21f",  # pragma: allowlist secret
        "type": "Jinja",
        "files": ["chat_template.jinja", "tokenizer_config.json"],
        "loading_path": "Pinned chat_template.jinja rendered by the standard template path.",
    },
    "MiniMaxAI/MiniMax-M2.7": {
        "revision": "d494266a4affc0d2995ba1fa35c8481cbd84294b",  # pragma: allowlist secret
        "type": "Jinja",
        "files": ["chat_template.jinja", "tokenizer_config.json"],
        "loading_path": "Pinned chat_template.jinja rendered by the standard template path.",
    },
    "MiniMaxAI/MiniMax-M3": {
        "revision": "f0e1c1e04d40177e4673a22097036854f536e9c0",  # pragma: allowlist secret
        "type": "Jinja",
        "files": ["chat_template.jinja", "tokenizer_config.json"],
        "loading_path": "Pinned chat_template.jinja rendered by the standard template path.",
    },
}

PROBES = {
    "control_no_system": [
        {"role": "user", "content": "Q"},
        {"role": "user", "content": "Q2"},
    ],
    "control_leading_system": [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "Q"},
    ],
    "primary_inline_system": [
        {"role": "user", "content": "Q"},
        {"role": "system", "content": "LATESYS"},
        {"role": "user", "content": "Q2"},
    ],
    "tool_boundary_no_system": [
        {"role": "user", "content": "Q"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "lookup", "arguments": {"key": "x"}},
            }],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "RESULT"},
        {"role": "user", "content": "Q2"},
    ],
    "tool_boundary_inline_system": [
        {"role": "user", "content": "Q"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "lookup", "arguments": {"key": "x"}},
            }],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "RESULT"},
        {"role": "system", "content": "LATESYS"},
        {"role": "user", "content": "Q2"},
    ],
}

TOOLS = [{
    "type": "function",
    "function": {
        "name": "lookup",
        "description": "Return a value for a key.",
        "parameters": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
    },
}]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(model: str, revision: str, name: str) -> tuple[bytes, str]:
    url = f"https://huggingface.co/{model}/resolve/{revision}/{name}"
    request = urllib.request.Request(url, headers={"User-Agent": "minefield-evidence/1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read(), url


def error_record(exc: BaseException) -> dict[str, Any]:
    return {
        "status": "REJECTED",
        "exception_class": type(exc).__name__,
        "error": str(exc),
        "traceback_tail": traceback.format_exc().splitlines()[-8:],
    }


def render_jinja(template: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        rendered, _ = render_jinja_template(
            [messages],
            tools=TOOLS,
            chat_template=template,
            add_generation_prompt=True,
        )
        return {"status": "EXECUTED", "rendered_text": rendered[0]}
    except Exception as exc:
        return error_record(exc)


def tokenizer_render(tokenizer: Any, messages: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        rendered = tokenizer.apply_chat_template(
            messages,
            tools=TOOLS,
            tokenize=False,
            add_generation_prompt=True,
        )
        ids = tokenizer.apply_chat_template(
            messages,
            tools=TOOLS,
            tokenize=True,
            add_generation_prompt=True,
        )
        if hasattr(ids, "tolist"):
            ids = ids.tolist()
        if isinstance(ids, dict):
            ids = ids["input_ids"]
        if ids and isinstance(ids[0], list):
            ids = ids[0]
        return {
            "status": "EXECUTED",
            "rendered_text": rendered,
            "token_ids": ids,
            "token_strings": tokenizer.convert_ids_to_tokens(ids),
            "decoded_from_token_ids": tokenizer.decode(
                ids, skip_special_tokens=False
            ),
        }
    except Exception as exc:
        return error_record(exc)


def remote_module_records() -> list[dict[str, Any]]:
    records = []
    for name, module in sorted(sys.modules.items()):
        file_name = getattr(module, "__file__", None)
        if not file_name or "transformers_modules" not in file_name:
            continue
        path = Path(file_name)
        if path.suffix != ".py" or not path.is_file():
            continue
        data = path.read_bytes()
        records.append({
            "module": name,
            "path_suffix": "/".join(path.parts[-5:]),
            "sha256": sha256(data),
        })
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--vllm-root", required=True)
    parser.add_argument("--execute-kimi-k3", action="store_true")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    vllm_root = Path(args.vllm_root).resolve(strict=True)

    report: dict[str, Any] = {
        "schema_version": "1.0",
        "_detect_secrets_review": (
            "pragma: allowlist secret - public immutable revisions and file "
            "digests, not credentials"
        ),
        "base_main": "8e969c419bad9ef8263fde2560c7dd0d19755686",  # pragma: allowlist secret
        "vllm_revision": VLLM_REVISION,
        "kimi_k3_support_revision": KIMI_SUPPORT_REVISION,
        "evidence_policy": {
            "jinja": "TOKENIZER_EXECUTED_AT_PINNED_REVISION",
            "kimi_k3": "TOKENIZER_EXECUTED_AT_PINNED_REVISION",
            "kimi_k3_vllm_endpoint": "UNDER_TEST",
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_only": os.environ.get("CUDA_VISIBLE_DEVICES") == "",
            "packages": {
                name: importlib.metadata.version(name)
                for name in (
                    "transformers",
                    "tokenizers",
                    "tiktoken",
                    "huggingface-hub",
                    "jinja2",
                    "safetensors",
                )
            },
        },
        "probes": PROBES,
        "models": {},
    }

    for model, spec in MODELS.items():
        files = {}
        bodies = {}
        for name in spec["files"]:
            data, url = fetch(model, spec["revision"], name)
            bodies[name] = data
            files[name] = {
                "url": url,
                "bytes": len(data),
                "sha256": sha256(data),
            }
        item = {
            "revision": spec["revision"],
            "template_type": spec["type"],
            "loading_path": spec["loading_path"],
            "files": files,
            "evidence_surface": "SOURCE_INSPECTED_AT_PINNED_REVISION",
        }
        if "chat_template.jinja" in bodies:
            template = bodies["chat_template.jinja"].decode("utf-8")
            item["executed_renders"] = {
                name: render_jinja(template, messages)
                for name, messages in PROBES.items()
            }
            item["evidence_surface"] = "TOKENIZER_EXECUTED_AT_PINNED_REVISION"
        report["models"][model] = item

    vllm_files = {}
    for name in (
        "vllm/tokenizers/deepseek_v4_encoding.py",
        "vllm/tokenizers/deepseek_v4.py",
        "vllm/tokenizers/registry.py",
        "vllm/renderers/kimi_k3.py",
        "vllm/entrypoints/anthropic/protocol.py",
        "vllm/entrypoints/anthropic/serving.py",
        "vllm/entrypoints/openai/chat_completion/protocol.py",
    ):
        path = vllm_root / name
        data = path.read_bytes()
        entry = {"sha256": sha256(data), "bytes": len(data)}
        if name.endswith("deepseek_v4_encoding.py"):
            entry["md5_lf_git_content"] = hashlib.md5(data).hexdigest()
            entry["md5_crlf_worktree"] = hashlib.md5(
                data.replace(b"\n", b"\r\n")
            ).hexdigest()
        vllm_files[name] = entry
    report["vllm_files"] = vllm_files

    if args.execute_kimi_k3:
        model = "moonshotai/Kimi-K3"
        revision = MODELS[model]["revision"]
        tokenizer = AutoTokenizer.from_pretrained(
            model,
            revision=revision,
            trust_remote_code=True,
        )
        item = report["models"][model]
        item["tokenizer_class"] = (
            f"{tokenizer.__class__.__module__}.{tokenizer.__class__.__qualname__}"
        )
        item["executed_renders"] = {
            name: tokenizer_render(tokenizer, messages)
            for name, messages in PROBES.items()
        }
        item["imported_remote_files"] = remote_module_records()
        item["evidence_surface"] = "TOKENIZER_EXECUTED_AT_PINNED_REVISION"
    else:
        report["models"]["moonshotai/Kimi-K3"]["evidence_surface"] = "UNDER_TEST"

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            report, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
