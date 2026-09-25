"""Rank registry entries without converting textual similarity into proof."""

from __future__ import annotations

import math
import re
from typing import Any

from .diagnosis_contract import contract_for_match, miss_contract
from .leads import search_leads

TOKEN_RE = re.compile(r"[a-z0-9_.+-]{2,}", re.I)
# Function words and conversational filler. Without these, "how do I ..."
# supplied two "concepts" on its own and off-domain questions (baking bread,
# centering a div) returned serving traps. Domain words that look ordinary
# but carry meaning here (stop, length, empty, off, first, same, cold) are
# deliberately NOT listed.
STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "into", "only",
    "your", "you", "use", "using", "not", "are", "was", "were", "has",
    "have", "under", "over", "after", "before",
    "a", "an", "am", "as", "at", "be", "been", "being", "but", "by", "can",
    "could", "did", "do", "does", "doing", "done", "each", "even", "ever",
    "had", "he", "her", "here", "him", "his", "how", "if", "in", "is", "it",
    "its", "just", "me", "my", "mine", "no", "of", "on", "or", "our", "out",
    "she", "should", "so", "some", "such", "than", "their", "them", "then",
    "there", "these", "they", "those", "to", "too", "up", "us", "very",
    "we", "what", "when", "where", "which", "while", "who", "whom", "why",
    "will", "would", "yet", "also", "any", "all", "about", "again", "get",
    "gets", "getting", "got", "keep", "keeps", "kept", "make", "makes",
    "made", "way", "best", "good", "really", "still", "now", "one", "thing",
    "things", "something", "anything", "everything", "someone", "anyone",
    "i", "im", "ive", "dont", "doesnt", "didnt", "cant", "wont", "isnt",
    "please", "help", "need", "want", "trying", "tried", "try", "like",
    "seems", "seem", "looks", "look", "happen", "happens", "happening",
}

# User phrasing may vary, but one concept still counts as one concept:
# aliases broaden vocabulary without manufacturing extra overlap.
TOKEN_ALIASES: dict[str, set[str]] = {
    "response": {"content", "reply"},
    "reply": {"content", "response"},
    "blank": {"empty"},
    "garbage": {"gibberish", "garbled", "nonsense"},
    "garbled": {"gibberish", "garbage", "nonsense"},
    "gibberish": {"garbage", "garbled", "nonsense"},
    "nonsense": {"garbage", "garbled", "gibberish"},
    "thinking": {"reasoning"},
    "reasoning": {"thinking"},
    "leak": {"spill", "spills", "spilled", "leaked", "leaking"},
    "leaked": {"spill", "spills", "spilled", "leak", "leaking"},
    "leaking": {"spill", "spills", "spilled", "leak", "leaked"},
    "ignored": {"inert"},
    "ignore": {"inert"},
}


def _stem(token: str) -> str:
    """Fold common English inflections so "restarted" meets "restart".

    Deliberately crude and symmetric: the same folding runs on the query and
    on the registry text, so it only has to be consistent, not linguistic.
    Identifiers with digits or punctuation (nvfp4, max_tokens, 0.26) are left
    exactly as written.
    """
    if not token.isalpha() or len(token) <= 4:
        return token
    if token.endswith("ies") and len(token) > 5:
        token = token[:-3] + "y"
    elif token.endswith("ing") and len(token) > 6:
        token = token[:-3]
    elif token.endswith("ed") and len(token) > 5:
        token = token[:-2]
    elif token.endswith("s") and not token.endswith("ss"):
        token = token[:-1]
    if token.endswith("e") and len(token) > 4:
        token = token[:-1]
    return token


def _tokens(value: str) -> set[str]:
    return {
        _stem(token.lower())
        for token in TOKEN_RE.findall(value)
        if token.lower() not in STOPWORDS
    }


def _concepts(value: str) -> list[set[str]]:
    """Return one alias-set per original meaningful token.

    Counting concepts rather than expanded tokens is deliberate: the word
    thinking may expand to reasoning, but that still contributes only one
    overlap. This prevents a synonym table from recreating the old
    one-shared-word false-positive bug.
    """
    out: list[set[str]] = []
    seen: set[str] = set()
    for token in TOKEN_RE.findall(value):
        token = token.lower()
        if token in STOPWORDS:
            continue
        stemmed = _stem(token)
        if stemmed in seen:
            continue  # "cache ... cached" is one concept, not two
        seen.add(stemmed)
        out.append({stemmed, *(_stem(a) for a in TOKEN_ALIASES.get(token, ()))})
    return out


def _concept_overlap(concepts: list[set[str]], searchable: set[str]) -> int:
    return sum(1 for concept in concepts if concept & searchable)


# A question must say something about model serving before textual
# resemblance can nominate a trap: "best running shoes for flat feet" shares
# two rare registry words and nothing else. Anchors are domain vocabulary
# (stems, matched after _stem) plus any identifier-looking token such as
# max_tokens, gfx1151, nvfp4 or sm120. This list describes the domain; it is
# not fitted to the benchmark's negatives.
DOMAIN_ANCHORS = frozenset((
    # serving stacks and runtimes
    "vllm", "sglang", "llama.cpp", "llamacpp", "llama", "ollama", "mlx", "mlx_lm", "tgi",
    "tensorrt", "trtllm", "lmstudio", "tabbyapi", "exllama", "transformers", "gguf",
    "nccl", "rdma", "ray", "cuda", "rocm", "hip", "triton", "flashinfer", "docker",
    "container", "kubernetes", "systemd", "cgroup", "huggingface", "hf",
    # hardware
    "gpu", "gpus", "vram", "nvidia", "amd", "radeon", "blackwell", "spark", "dgx",
    "gb10", "rtx", "strix", "kernel", "kernels", "driver", "nic", "hca", "oom",
    "memory", "unified",
    # model and inference vocabulary
    "model", "models", "llm", "checkpoint", "weights", "shard", "shards", "quant",
    "quantized", "quantization", "dequant", "fp4", "fp8", "bf16", "int4", "awq", "gptq",
    "moe", "expert", "experts", "token", "tokens", "tokenizer", "tokenize", "prompt",
    "prompts", "context", "prefill", "decode", "decoding", "inference", "serve",
    "serving", "server", "endpoint", "api", "openai", "request", "requests", "batch",
    "batching", "concurrency", "concurrent", "throughput", "latency", "tok",
    "cache", "cached", "caching", "kv", "prefix", "attention", "sdpa", "flash",
    "sliding", "window", "speculative", "draft", "drafter", "mtp", "ngram", "eagle",
    "temperature", "sampling", "logprobs", "perplexity", "greedy", "seed",
    "reasoning", "thinking", "think", "effort", "template", "jinja", "chat",
    "system", "assistant", "tool", "tools", "tool_calls", "function", "json",
    "schema", "parser", "stream", "streaming", "sse", "delta", "content",
    "completion", "completions", "finish_reason", "multimodal", "image", "audio",
    "embedding", "embeddings", "benchmark", "benchmarks", "bench", "eval", "evals",
    "harness", "lm-eval", "mmlu", "gsm8k", "score", "scores", "agent", "agents",
    "rollout", "rollouts", "finetune", "finetuned", "abliterated", "revision",
    "layer", "layers", "norm", "offload", "slot", "slots", "rank", "ranks",
    "tensor", "parallel", "multi-node", "node", "nodes", "port", "restart",
    "launch", "flag", "flags", "config", "soak", "canary", "leak",
    # what a model produces
    "output", "outputs", "answer", "answers", "response", "responses", "reply",
    "replies", "generation", "generations", "generate", "gibberish", "garbled",
    # measurement and operations vocabulary
    "baseline", "a/b", "ablation", "deterministic", "nondeterministic",
    "reproducible", "reproducibility", "probe", "pipeline", "install", "wheel",
    "http", "exit", "status", "healthcheck", "health", "readiness",
    "400", "404", "422", "500", "502", "503", "4xx", "5xx", "137",
    # consumer GPU model numbers people name instead of an architecture
    "3060", "3080", "3090", "4070", "4080", "4090", "5070", "5080", "5090",
    "a100", "h100", "h200", "b200", "mi300",
))


def _is_anchor(stemmed: str) -> bool:
    if stemmed in _DOMAIN_ANCHOR_STEMS:
        return True
    # identifier-looking: a letter plus a digit or underscore (nvfp4, sm120,
    # max_tokens, gfx1151). Bare numbers do not count.
    return bool(re.search(r"[a-z]", stemmed)) and bool(re.search(r"[0-9_]", stemmed))


# Minimum rarity-weighted evidence for an ordinary textual candidate, in units
# of "one word unique to a single entry", so it means the same thing for the
# 143-entry registry and a 3-entry test fixture. Two generic shared words fall
# below it; two reasonably specific ones clear it. Chosen on the benchmark's
# tune split (benchmarks/symptom_queries.json), reported on holdout.
MIN_EVIDENCE = 1.15


_DOMAIN_ANCHOR_STEMS = {_stem(term) for term in DOMAIN_ANCHORS}


_INDEX_CACHE: dict[str, tuple[list[tuple[set[str], set[str], set[str]]], dict[str, float]]] = {}

# A word that matches the trap's title counts for more than one buried in the
# symptom paragraph: the title is the entry's own one-line summary.
TITLE_BOOST = 1.5


def _index(registry: dict[str, Any]) -> tuple[list[tuple[set[str], set[str], set[str]]], dict[str, float]]:
    """Per-entry token sets plus an inverse-document-frequency table.

    A word that appears in most entries ("model", "server") tells you little
    about which trap you hit; one that appears in two ("nvfp4", "orphan")
    tells you a lot. Cached per registry content hash.
    """
    key = str(registry.get("content_sha256") or id(registry))
    cached = _INDEX_CACHE.get(key)
    if cached is not None:
        return cached
    per_entry: list[tuple[set[str], set[str], set[str]]] = []
    df: dict[str, int] = {}
    for entry in registry["entries"]:
        symptom_tokens = _tokens(entry["symptom"] + " " + entry["title"] + " " + entry["check"])
        context_tokens = _tokens(
            " ".join(entry["affected_stacks"])
            + " " + entry["affected_versions_builds"]
            + " " + entry["mechanism"]
        )
        per_entry.append((symptom_tokens, context_tokens, _tokens(entry["title"])))
        for token in symptom_tokens:
            df[token] = df.get(token, 0) + 1
    n = max(1, len(per_entry))
    # Normalised so a word found in exactly one entry weighs 1.0.
    top = math.log((n + 1) / 2) + 1.0
    idf = {
        token: (math.log((n + 1) / (count + 1)) + 1.0) / top
        for token, count in df.items()
    }
    _INDEX_CACHE[key] = (per_entry, idf)
    return per_entry, idf


def _concept_weight(
    concepts: list[set[str]],
    searchable: set[str],
    idf: dict[str, float],
    title: set[str] = frozenset(),
) -> float:
    total = 0.0
    for concept in concepts:
        hit = concept & searchable
        if hit:
            total += max(idf.get(token, 0.0) for token in hit) * (
                TITLE_BOOST if concept & title else 1.0
            )
    return total


def search(
    registry: dict[str, Any],
    symptom: str,
    *,
    stack: str | None = None,
    model: str | None = None,
    version: str | None = None,
    log_excerpt: str | None = None,
    conditions: dict[str, Any] | None = None,
    direct_probe_trap_ids: list[str] | None = None,
    direct_probe_results: dict[str, str] | None = None,
    mechanism_probe_trap_ids: list[str] | None = None,
    evidence_status: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    conditions = dict(conditions or {})
    if stack:
        conditions.setdefault("serving_stack", stack)
    if model:
        conditions.setdefault("exact_checkpoint", model)
    if version:
        conditions.setdefault("stack_version", version)
    known_ids = {entry["id"] for entry in registry["entries"]}
    direct_ids = {
        str(item).zfill(2) for item in (direct_probe_trap_ids or [])
        if str(item).zfill(2) in known_ids
    }
    probe_results = {
        str(trap_id).zfill(2): str(outcome).lower()
        for trap_id, outcome in (direct_probe_results or {}).items()
        if (
            str(trap_id).zfill(2) in known_ids
            and str(outcome).lower() in {"confirmed", "refuted", "inconclusive"}
        )
    }
    explicit_ids = direct_ids | set(probe_results)
    mechanism_ids = {str(item).zfill(2) for item in (mechanism_probe_trap_ids or [])}

    # Candidate admission is symptom-first. Stack/model/version may improve
    # ranking and applicability, but cannot turn one ordinary shared word into
    # a candidate by themselves.
    symptom_text_for_match = " ".join(
        part for part in (symptom, log_excerpt or "") if part
    )
    symptom_concepts = _concepts(symptom_text_for_match)
    on_topic = any(_is_anchor(token) for concept in symptom_concepts for token in concept)
    context_concepts = _concepts(" ".join(filter(None, (stack, model, version))))

    per_entry, idf = _index(registry)
    results: list[dict[str, Any]] = []
    for entry, (searchable_symptom_tokens, searchable_context_tokens, title_tokens) in zip(
        registry["entries"], per_entry
    ):
        if evidence_status and evidence_status not in entry["evidence_strength"]:
            continue
        searchable_symptom = (
            entry["symptom"] + " " + entry["title"] + " " + entry["check"]
        )
        direct = _concept_overlap(symptom_concepts, searchable_symptom_tokens)
        context = _concept_overlap(context_concepts, searchable_context_tokens)
        is_explicit = entry["id"] in explicit_ids

        # Two independently supplied meaningful symptom/log concepts are the
        # minimum for ordinary textual admission. Direct-probe IDs bypass this
        # because the caller explicitly named the trap under test.
        if (direct < 2 or not on_topic) and not is_explicit:
            continue
        weight = _concept_weight(symptom_concepts, searchable_symptom_tokens, idf, title_tokens)
        if weight < MIN_EVIDENCE and not is_explicit:
            continue

        # Rarity-weighted: two specific shared words outrank four generic
        # ones. Scaled so a typical shared word is worth about 4 points, the
        # same order as the previous flat per-concept score.
        score = round(weight * 7) + context
        normalized_symptom = symptom.strip().lower()
        if (
            normalized_symptom
            and len(_concepts(symptom)) >= 2
            and normalized_symptom in searchable_symptom.lower()
        ):
            score += 30
        if stack:
            target = stack.lower()
            if any(
                target in item.lower() or item.lower() in target
                for item in entry["affected_stacks"]
            ):
                score += 5
        if model:
            target = model.lower()
            if any(
                target in item.lower() or item.lower() in target
                for item in entry["affected_models"]
            ):
                score += 5
        if version:
            if version.lower() in entry["affected_versions_builds"].lower():
                score += 3
        probe_result = probe_results.get(
            entry["id"],
            "candidate_requested" if entry["id"] in direct_ids else "not_supplied",
        )
        contract = contract_for_match(
            entry,
            observed_symptom=symptom,
            symptom_score=score,
            observed_conditions=conditions,
            direct_probe_support=probe_result == "confirmed",
            direct_probe_result=probe_result,
            mechanism_directly_supported=entry["id"] in mechanism_ids,
        )
        results.append({
            "trap_ids": [entry["id"]],
            "title": entry["title"],
            "match_confidence": contract["diagnosis_level"],
            "score": score,
            "evidence_weight": round(weight, 2),
            "source_path": entry["source_path"],
            **contract,
        })
    results.sort(key=lambda item: (
        item["trap_id"] not in explicit_ids,
        -item["score"],
        int(item["trap_ids"][0]),
    ))
    explicit_results = [item for item in results if item["trap_id"] in explicit_ids]
    ordinary_results = [item for item in results if item["trap_id"] not in explicit_ids]
    ordinary_slots = min(max(1, limit), max(0, 50 - len(explicit_results)))
    return explicit_results[:50] + ordinary_results[:ordinary_slots]


def diagnose(
    registry: dict[str, Any],
    symptom: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Return canonical candidates plus a clearly separate weaker lead layer.

    Canonical traps are always searched first. L-series leads remain
    non-canonical and never turn resemblance into confirmation.
    """
    matches = search(registry, symptom, **kwargs)
    lead_text = " ".join(
        part for part in (symptom, kwargs.get("log_excerpt") or "") if part
    )
    # The lead tier gets the same on-topic gate as canonical traps, so an
    # off-domain question ("how do I bake bread") returns nothing at all.
    on_topic = any(_is_anchor(token) for concept in _concepts(lead_text) for token in concept)
    lead_matches = search_leads(
        lead_text,
        stack=kwargs.get("stack"),
        model=kwargs.get("model"),
        version=kwargs.get("version"),
        limit=5,
    ) if on_topic else []
    if not matches:
        result = miss_contract(symptom, kwargs.get("conditions"))
        result["possible_unverified_leads"] = lead_matches
        if lead_matches:
            result["warning"] = (
                "No canonical Minefield trap matched. The L-series items below are "
                "possible unverified troubleshooting leads only. Run their confirm/refute "
                "checks before treating any mechanism as applicable."
            )
        else:
            result["warning"] = (
                "No canonical trap or public-safe unverified lead matched. A registry miss "
                "means not documented, never safe."
            )
        return result
    return {
        "diagnosis_level": matches[0]["diagnosis_level"],
        "observed_symptom": symptom,
        "matches": matches,
        "possible_unverified_leads": lead_matches,
        "warning": (
            "Canonical candidates are ranked, not proven. L-series suggestions are a "
            "strictly weaker non-canonical tier. Apply mitigations only after the relevant "
            "confirmation check succeeds under the user's exact conditions."
        ),
    }
