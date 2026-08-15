# 2026-08-15 — Qwen3.8 reasoning/template configuration traps (first-party)

**Independently reproduced here by Blackwellboy** on a pinned local
serving artifact. Prior public report / lead: **TheTom/offlabel**.

This note is the public mining surface for a private campaign on
RTX 5090 that also exercised a 262144-context SGLang profile. The
**template-control** claims are re-derivable offline from the vendored
fixture. Campaign raw logs remain private; they are not required to
re-run the public check.

## Pin

| field | value |
|---|---|
| checkpoint | `RadixArk/Qwen3.8-27B-NVFP4` |
| revision | `52d1adc5f38aa5ebf099c29ed7025ba34cfbb854` |
| `chat_template.jinja` SHA256 | `c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041` |
| runtime exercised | `lmsysorg/sglang:qwen38-27b` digest `sha256:febfb971…` |
| context on the measured lane | CONFIG 262144 / KV capacity 263461 |

## Disposition vs existing registry entries

Do **not** allocate four new trap numbers for four symptoms.

| mechanism | disposition | existing entry |
|---|---|---|
| unset `reasoning_effort` → **xhigh** when thinking on | **extension / corroboration** | [trap 03](../traps/reasoning/03-enable-thinking-default-drift.md) |
| `medium` accepted, no instruction branch | **extension / subcase** | [trap 07](../traps/reasoning/07-reasoning-effort-silently-ignored.md) |
| `preserve_thinking` defaults **true** and replays history | **extension** (polarity note) | [trap 04](../traps/template/04-history-reasoning-stripping.md) |
| empty `<think></think>` on content-only priors | **corroboration / subcase** | [trap 25](../traps/template/25-empty-think-blocks-poison-prefix-cache.md) |

## Public check

```bash
python3 checks/reproduce_qwen38_reasoning_config_traps.py
```

Fixture (Apache-2.0 source checkpoint LICENSE):
`checks/fixtures/qwen38_nvfp4_52d1adc/`.

## Attribution

- Independent first-party reproduction and measurements: **Blackwellboy**
- Prior public report / lead: **TheTom/offlabel**
