# Trap 21: no generation_config.json means your server's built-ins silently become "the model's settings"

**Found by Blackwellboy.**

**Status: reproduced here** (two llama.cpp lanes, one positive and one negative control, measured via `/props`).

**Symptom.** Your numbers on a model differ from everyone else's "at
defaults", or a model underperforms its reputation, and every config you
wrote looks correct because you wrote none: you trusted the defaults. Which
defaults you actually got depends on what the checkpoint shipped, and some
checkpoints ship nothing.

**Mechanism.** Some model repos carry no `generation_config.json` at all,
with the recommended sampling stated only in README prose. Nothing
machine-readable flows into the GGUF conversion or the server, so the
server's built-in defaults win silently. The card's recommendations can
differ from those built-ins on every axis at once.

Measured case, Qwen3.5-9B (repo ships no `generation_config.json`; card
README recommends per-mode sampling in prose, including `top_k=20`,
`min_p=0.0`, `presence_penalty=1.5`, temperature 0.7 to 1.0 by mode):
the serving lane's effective defaults, read live from `/props`, were
**temperature 0.8, top_k 40, min_p 0.05, presence_penalty 0.0**, llama.cpp's
own built-ins. Five parameters differ from the card's recommendation for
every mode, including a presence penalty of 1.5 that no default-config user
will ever run.

Negative control on the same stack: Qwen3.6-27B ships a
`generation_config.json` (temperature 1.0, top_k 20, top_p 0.95), and the
serving lane's `/props` defaults matched it exactly. The trap is the
missing file, not the server.

**Stacks and builds bitten.** llama.cpp `b9066` serving Qwen3.5-9B Q4_K_M
(defaults diverge); llama.cpp `b9193` serving Qwen3.6-27B Q4_K_M (defaults
match; control). The class applies to any server with built-in sampling
defaults and any checkpoint that documents sampling only in prose.

**The check.** Two commands:

```bash
curl -s localhost:PORT/props | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['default_generation_settings']['params'])"
curl -s https://huggingface.co/<repo>/resolve/main/generation_config.json
```

If the second returns "Entry not found", read the card's prose
recommendation and compare it to the first, parameter by parameter. Also
note which mode the recommendation is for; thinking and non-thinking
recommendations differ.

**The fix.** Set sampling explicitly on every request (or in the serve
line), taken from the card, per mode. Never describe a run as "at model
defaults" for a checkpoint that ships no generation config; there is no
such thing on that model.

**Found.** 2026-07-27, standardized probe sweep.

**Attribution.** Blackwellboy. Probe JSONs in the sweep results
(`probe_qwen35-9b*.json`, `probe_qwen36-27b*.json`).
