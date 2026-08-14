# Inline-system pinned evidence, 2026-07-30

This folder preserves the executable evidence behind Trap 113 and the narrow
Trap 56 addendum.

- `raw-executed-render-manifest.json` contains immutable source URLs, SHA-256
  values, exact probes, raw generic-Transformers Jinja renders, and the
  isolated Kimi-K3 tokenizer
  result with IDs, token strings, decoded text, imported remote files, and
  package versions.
- `classification-matrix.json` contains the exact classifier manifests and
  results.
- `scripts/capture_pinned_evidence.py` reproduces the source fetch and render
  capture.
- `scripts/classify_captured_evidence.py` performs the offline classification.

The run used no model-serving endpoint or fleet node. Kimi-K3 vLLM runtime
verification remains `UNDER_TEST`. The explicit remote-code exception was
limited to Kimi-K3 revision
`9f62e4e9fffbd0a83ddd60e1c209d828994b3569`, inside a disposable CPU-only
profile with a dedicated cache and no host secrets.

The GLM, Kimi-K2.6 and MiniMax rows are
`TEMPLATE_EXECUTED_AT_PINNED_REVISION`: their fetched Jinja was executed
directly by the generic Transformers renderer. They are not labelled tokenizer
or endpoint execution. Kimi-K3 alone used its pinned checkpoint tokenizer
class and remains strict `INCONCLUSIVE` because decoded representations differ.

The source map and pins were contributed by
[@wqh17101](https://github.com/wqh17101), with explicit publication and
attribution permission in
[vLLM issue #46710](https://github.com/vllm-project/vllm/issues/46710#issuecomment-5131158274).
The registry fetched and executed the public artifacts independently, so the
run is not labelled contributor-measured.
