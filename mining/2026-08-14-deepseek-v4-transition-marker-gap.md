# DeepSeek-V4 transition-marker gap, 2026-08-14

**Disposition: extension of traps 56 and 113, not a new trap ID.**

## Source

On 2026-08-14, [@flexwang](https://github.com/flexwang) added a render-level
reproduction to [vLLM issue #46710](https://github.com/vllm-project/vllm/issues/46710#issuecomment-5289436964).
The useful new part is not the already-known late-system welding by itself. It
is the transition immediately after it: an assistant turn can lose its
`<｜Assistant｜>` marker, and the same shape is reachable with adjacent assistant
messages even if inline system messages are merged away.

## Reported render

With tools declared so prior reasoning is retained, the preserve-in-place arm
was reported as:

```text
<｜begin▁of▁sentence｜>SYS\n\n[TOOLS BLOCK]\n<｜User｜>q1INLINE_SYS_REMINDERr1</think>a1<｜end▁of▁sentence｜><｜User｜>q2<｜Assistant｜><think>
```

The merge arm was:

```text
<｜begin▁of▁sentence｜>SYS\nINLINE_SYS_REMINDER\n\n[TOOLS BLOCK]\n<｜User｜>q1<｜Assistant｜><think>r1</think>a1<｜end▁of▁sentence｜><｜User｜>q2<｜Assistant｜><think>
```

Three structural differences matter:

1. `INLINE_SYS_REMINDER` is welded directly to `q1` with no delimiter.
2. The assistant turn after that system message has no `<｜Assistant｜>` marker.
3. Its retained reasoning becomes `r1</think>` without an opening `<think>`, so
   the reasoning bytes sit in the previous span before a dangling close tag.

[@flexwang](https://github.com/flexwang) also reports reproducing the same
missing-marker shape from two consecutive assistant messages, and reports the
same result from the checkpoint's reference `encoding_dsv4.py`. That makes the
new observation broader than the vLLM inline-system policy alone.

**Status of the reported renders: reported by others.** This registry has not
run the exact message sequences above against a live endpoint in this pass.

## Independent source inspection

The registry independently inspected current vLLM `main` at
[`8e6d8e4f6a0c84db0d79129ab648492edf640fe2`](https://github.com/vllm-project/vllm/tree/8e6d8e4f6a0c84db0d79129ab648492edf640fe2).
At that revision,
[`vllm/tokenizers/deepseek_v4_encoding.py`](https://github.com/vllm-project/vllm/blob/8e6d8e4f6a0c84db0d79129ab648492edf640fe2/vllm/tokenizers/deepseek_v4_encoding.py)
still has both sides of the reported mechanism:

```python
system_msg_template: str = "{content}"
```

and the system branch emits that bare content:

```python
if role == "system":
    prompt += system_msg_template.format(content=content or "")
```

while the ordinary Assistant transition is appended only when the current
message is a user or developer turn:

```python
elif messages[index].get("role") in ["user", "developer"]:
    prompt += ASSISTANT_SP_TOKEN
```

So the source-level reading is confirmed at this pinned revision: a
non-user/developer role immediately before an assistant is not covered by the
normal transition branch. This is **source inspection**, not an endpoint or
quality reproduction.

## Relation to PR #47681

[PR #47681](https://github.com/vllm-project/vllm/pull/47681) is still open and
unmerged as of this note. Its current design is broader than its original July
revision: `merge` is the default for inline system messages across the shared
OpenAI/Anthropic path, with explicit `preserve` opt-in.

That policy removes the dangerous inline-system route for default callers, but
it does not by itself prove that the encoder's general role-transition logic is
safe. In particular, the adjacent-assistant reproduction does not need an
inline system message at all.

Two regressions would separate the policy fix from the encoder boundary:

```text
[user, system, assistant(reasoning), user]
[user, assistant, assistant(reasoning), user]
```

For each, inspect the rendered prompt and assert that every assistant turn has
the expected assistant boundary and balanced reasoning delimiters.

## Claim boundary

This note does **not** claim that the missing marker is the sole cause of the
end-to-end degradation reported in issue #46710. The issue also contains a
128-token sliding-window-attention analysis, and the mechanisms can coexist.
What is established here is narrower: the encoded prompt has an independently
visible structural defect before attention is involved.

No end-to-end quality A/B isolating only this marker gap has been run by this
registry. Until one exists, the correct statement is **malformed render**, not
"proved root cause of output corruption."

## Registry routing

- [Trap 56](../traps/template/56-checkpoint-ships-no-chat-template.md) owns the
  DeepSeek-specific Python-encoder and unmarked-system behavior.
- [Trap 113](../traps/template/113-inline-system-role-is-not-a-stable-contract.md)
  owns the broader contract lesson that accepted message roles are not proof of
  preserved role boundaries.
- No new trap number is allocated for this source/render extension.

**Attribution.** New transition-marker observation and adjacent-assistant
reproduction: [@flexwang](https://github.com/flexwang). Original DeepSeek live
late-system render: Blackwellboy. Earlier cross-model source map and pins:
[@wqh17101](https://github.com/wqh17101).
