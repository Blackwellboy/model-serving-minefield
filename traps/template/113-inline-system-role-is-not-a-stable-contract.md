# Trap 113: inline system role is not a stable render contract

**Found by @wqh17101 and Blackwellboy.**

**Status: reproduced here** at the rendered-constructor boundary from immutable
public template and tokenizer artifacts, with raw executed renders and a
runnable classifier in
[`mining/2026-07-30-inline-system-evidence/`](../../mining/2026-07-30-inline-system-evidence/).
The live serving-endpoint reproduction in this entry is DeepSeek only; the
other rows do not claim endpoint acceptance.

**Symptom.** A constructor or serving API receives the same inline message
sequence:

```text
user "Q", system "LATESYS", user "Q2"
```

One checkpoint preserves `LATESYS` inside a distinct system span. Another
returns success but silently removes it. A third returns success after joining
it to the preceding user turn. Code that treats HTTP acceptance as proof of
system-role preservation gets three materially different prompts from the
same request.

**Mechanism.** Message validation and prompt construction are separate
contracts. Once an inline system message reaches a checkpoint-specific Jinja
template or Python encoder, that constructor may:

- emit a distinct system boundary: `ROLE_MARKED`;
- omit the message: `DROPPED`, which is non-welding but lossy;
- place the text inside a user span: `WELDED_TO_USER`;
- reject the sequence: `REJECTED`; or
- emit boundaries too weak or conflicting to classify safely.

The constructor, its immutable revision, and the serving entrypoint are
therefore part of the request semantics. Model output cannot distinguish these
cases reliably because it is downstream of the render.

**Stacks and builds bitten.** The 2026-07-30 public-artifact run executed exact
Jinja revisions through the generic Transformers template renderer (not
checkpoint tokenizer classes or serving endpoints) for GLM-5.1
`26e1bd6e011feb778d25ae34b09b07074139d92d`, GLM-5.2
`b4734de4facf877f85769a911abafc5283eab3d9`, Kimi-K2.6
`7eb5002f6aadc958aed6a9177b7ed26bb94011bb`, MiniMax-M2.5
`f710177d938eff80b684d42c5aa84b382612f21f`, MiniMax-M2.7
`d494266a4affc0d2995ba1fa35c8481cbd84294b`, and MiniMax-M3
`f0e1c1e04d40177e4673a22097036854f536e9c0`. The first three rendered
`ROLE_MARKED`; all three MiniMax revisions rendered `DROPPED` and exactly
matched their no-system controls. Both results also held after a tool result.

The existing live DeepSeek-V4-Flash `/tokenize` render in
[trap 56](56-checkpoint-ships-no-chat-template.md) is `WELDED_TO_USER`.
Kimi-K3 revision `9f62e4e9fffbd0a83ddd60e1c209d828994b3569` was executed through its
pinned upstream tokenizer in a CPU-only isolated profile. Its untokenized
render is visibly system-marked, but decoding the token IDs inserts spaces
around structural tokens. The strict cross-representation result is therefore
`INCONCLUSIVE`, and the actual vLLM endpoint remains `UNDER_TEST`.

**The check.** Capture three renders from the same immutable constructor: two
user turns with no system message, a leading system message plus one user
turn, and the inline sequence above. Add the same inline message after a tool
result. Preserve raw text, token strings and IDs where available. Then run:

```bash
minefield classify-inline-system --manifest evidence.json
```

`DROPPED` requires the target to be absent and the render to exactly match the
no-system control. `ROLE_MARKED` requires the target to sit inside a system
span whose marker also bounds the leading-system control. `WELDED_TO_USER`
requires every target occurrence to sit inside a user span. A marker copied
from user content, conflicting decoded forms, missing controls, or unclear
boundaries must remain `AMBIGUOUS` or `INCONCLUSIVE`.

**The fix.** Pin and record the template or encoder hash with the model
revision. Reject inline system messages at the application boundary unless
that exact constructor and entrypoint have passed the render probe. Where
inline messages are not supported, reject them or deliberately transform them
without lowering a developer/root instruction into a weaker tier. If the
runtime has only one system tier, merge only policy that already belongs to
that tier into its initial message and record the transformation; never rely
on silent template behavior. Treat `DROPPED` as instruction loss, not as a
safe non-welding result.

**Found.** 2026-07-30, while turning the source analysis in vLLM issue #46710
into pinned executable evidence and a bounded classifier.

**Attribution.** [@wqh17101](https://github.com/wqh17101) supplied the
cross-model source analysis, immutable pins, and explicit permission to
publish and credit it in
[vLLM issue #46710](https://github.com/vllm-project/vllm/issues/46710#issuecomment-5131158274).
Blackwellboy supplied the prior live DeepSeek render. The registry run
independently fetched, hashed, and executed the public artifacts; source
inspection is not described as contributor measurement.

## Added 2026-08-14: DeepSeek's next-role transition can lose the assistant marker

[@flexwang](https://github.com/flexwang) reported a second structural defect on
[vLLM issue #46710](https://github.com/vllm-project/vllm/issues/46710#issuecomment-5289436964)
while testing the current `deepseek_v4` encoder with prior reasoning retained.
After an inline system message, the following assistant turn was rendered
without `<｜Assistant｜>` and its reasoning appeared as `r1</think>` with no
opening `<think>`. He also reproduced the missing-marker shape using two
consecutive assistant messages, so this is not limited to the inline-system
policy.

The registry independently inspected vLLM `main` at
[`8e6d8e4f6a0c84db0d79129ab648492edf640fe2`](https://github.com/vllm-project/vllm/tree/8e6d8e4f6a0c84db0d79129ab648492edf640fe2).
At that revision the DeepSeek encoder still emits system messages as bare
`"{content}"`, and its ordinary Assistant transition is appended only from a
current role in `user` or `developer`. That source shape is consistent with the
reported render.

**Status of this addendum:** the exact renders and adjacent-assistant endpoint
behavior are **reported by others**; the current-source mechanism was
independently inspected here. We have not run an end-to-end quality A/B that
isolates this marker gap, so this is not claimed as the sole cause of issue
#46710's degraded output.

[PR #47681](https://github.com/vllm-project/vllm/pull/47681) now uses a shared
merge-by-default policy for inline system messages across OpenAI and Anthropic,
with explicit `preserve` opt-in. That removes the default late-system route but
cannot by itself close an adjacent-assistant path that contains no system
message. Add two render regressions when qualifying this encoder:

```text
[user, system, assistant(reasoning), user]
[user, assistant, assistant(reasoning), user]
```

For both, assert the expected assistant boundary and balanced reasoning
delimiters before using output quality as the diagnostic. Full source/render
notes and claim boundaries are preserved in
[`mining/2026-08-14-deepseek-v4-transition-marker-gap.md`](../../mining/2026-08-14-deepseek-v4-transition-marker-gap.md).

**Attribution for this extension:** [@flexwang](https://github.com/flexwang).
