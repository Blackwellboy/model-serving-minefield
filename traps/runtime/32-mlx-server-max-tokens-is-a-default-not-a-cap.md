# Trap 32: mlx_lm's server --max-tokens is a per-request default, not a cap

**Found by Blackwellboy.**

**Status: reproduced here** (one stack, single behavioral run,
source-confirmed on the running release and current main).

**Symptom.** You size a lane with a server-side token limit
(`--max-tokens 1024` in the launch flags), treat it as the lane's budget
ceiling, and a client request quietly runs past it.

**Mechanism.** The flag supplies the default for requests that omit
`max_tokens`. It is not an upper bound on requests that state their own.
Confirmed in source: mlx_lm's request handler resolves
`max_completion_tokens`, then `max_tokens`, and only then falls back to
`cli_args.max_tokens`; nothing clamps a client value against the flag
(checked at the running release v0.31.3 and current main, identical logic).
The flag's own help text says "Default maximum number of tokens to
generate", so upstream documents it as a default; the trap is that the
spelling `--max-tokens` reads like a cap, and nothing in the response
distinguishes "server clamped me" from "server obeyed me", so operators who
believe it is a cap get no signal that it is not.

**Measured** (2026-07-27, stock mlx_lm server 0.31.3, prism-ml
Ternary-Bonsai-27B-mlx-2bit, Apple silicon, temperature 0). Server launched
with `--max-tokens 1024`. A request with `max_tokens=1600` and a
keep-counting prompt returned HTTP 200, `finish_reason=length`,
`usage.completion_tokens=1600`. The client value won, 600 tokens past the
server flag, no warning, no clamp, no error. Wall time 167 s on a lane
whose normal replies take 1 to 2 s: that is the practical hazard, a single
request monopolizing a low-volume lane for minutes.

**Combined with
[trap 29](../reasoning/29-server-reasoning-off-is-not-an-off-switch.md) on
the same lane:** thinking-off (via `--chat-template-args`) and the token
limit are BOTH per-request defaults on this stack. A single client request
can turn thinking on AND raise its own budget. There is no server-side
resource gate at all; if you need one, it has to live in front of the
server.

**Stacks and builds bitten.** mlx-lm 0.31.3 (stock `mlx_lm server`),
behaviorally; the no-clamp resolution order is also present in current main
at the time of writing. Single version behaviorally tested; if a later
release adds a true cap flag, this entry should say so.

**The check.** Send one request with `max_tokens` greater than the server
flag and read `usage.completion_tokens`. Cheap, definitive, and worth doing
on any stack whose launch flags you are treating as guarantees.

**The fix.** Put the clamp in a gateway you control, or size the lane
assuming the largest `max_tokens` any client might send.

**Found.** 2026-07-27, MLX characterization pass.

**Attribution.** Blackwellboy. Related:
[trap 29](../reasoning/29-server-reasoning-off-is-not-an-off-switch.md)
(same theme one knob over),
[trap 12](../evaluation/12-empty-content-at-token-ceiling.md) (what a
blown budget looks like from the scoring side).
