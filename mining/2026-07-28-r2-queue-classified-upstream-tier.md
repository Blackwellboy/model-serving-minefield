# The round-2 queue, worked in full: 50 candidates, 11 published, 22 closed

**Date:** 2026-07-28. Desk work only, no lane, node or hardware contact.

Roughly fifty mined upstream candidates had been sitting unpublished, most of
them blocked as not-testable for want of a stack we do not run. Several were
maintainer-confirmed with reproductions in the thread. That is real information
a stranger could use, and while it sat in a private queue it helped nobody.

This pass read every candidate, **fetched and read the primary source for each
one that had one**, and classified it. Eleven were published into the new
[upstream-reported tier](../upstream/). Twenty-two were closed as too weak, so
they stop being re-queued. The rest were already covered or already settled.

---

## The finding that should change how the next mining round is used

**The mining summaries were wrong often enough that publishing from them would
have published false claims.** Not occasionally: on this queue, six candidates
across four classes (out of roughly thirty-five with a primary source we could
read) were materially misdescribed by their own summaries. That is nearer one
in six of the sourced set, not one in four of the whole round.

Four specific classes, all found by opening the tab:

1. **Resolved upstream as usage, described here as a live engine bug.** R2-23
   was ranked seventh of fifty as a well-attested vLLM scoring defect, and our
   own [blocked-candidates note](2026-07-27-r2-blocked-not-testable.md) carried
   a test plan to confirm it. The thread closes with **the reporter** saying
   the scores were fine once the chat template was supplied correctly. The
   correction is on that note now, and the durable trap that *is* there was
   published as [U10](../upstream/U10-vllm-vl-reranker-without-chat-template.md).
2. **Retracted by the reporter, still quoted.** R2-27's source #19545 is a
   two-day issue whose author wrote that "what I initially thought was a bug
   might not be a bug after all". The summary quoted its title as an
   establishment. R2-02's second bug is **struck through in the issue body**
   and was likewise carried forward as live.
3. **Cited for a claim the source does not make.** R2-24 and R2-49 both cite
   vLLM #33986 for embedding-quality regressions and pooling defaults. That
   issue is a maintainer's **tracking index**: a list of links to example
   scripts and sub-issues. It makes neither claim.
4. **Headline disputed by a maintainer, dispute not recorded.** R2-02's source
   #14493 was answered by a maintainer with "which is demonstrably incorrect"
   and a working session. The sibling claim in the same issue is still open and
   unanswered, and that is the one worth publishing,
   [U02](../upstream/U02-ollama-go-runner-drops-sampling-penalties.md), but
   only with the dispute stated.

A desk mining list is a **lead**. The tier's evidence bar now requires the
thread itself, with the date somebody opened it, and it is
[enforced](../integrity/upstream_integrity.py) rather than requested.

## What is now published, and what is not

**Published: 11 entries covering 12 candidates.** All eleven are in
[`upstream/`](../upstream/), which never enters Core, never counts toward
doctor coverage, and never counts toward the registry total.

| Candidate | Entry | Engagement | Issue state |
|---|---|---|---|
| R2-05 | [U01](../upstream/U01-ollama-toolcalls-missing-on-openai-route.md) | maintainer confirmed | open |
| R2-03 | [U02](../upstream/U02-ollama-go-runner-drops-sampling-penalties.md) | maintainer disputed (a sibling claim) | open |
| R2-02, R2-06 | [U03](../upstream/U03-ollama-bundled-template-diverges.md) | maintainer confirmed, twice | open / closed, fixed |
| R2-01 | [U04](../upstream/U04-ollama-vram-tiered-default-context.md) | maintainer responded | closed, not fixed |
| R2-04 | [U05](../upstream/U05-ollama-gemma4-think-false-leaks-json.md) | maintainer confirmed | closed, fixed |
| R2-07 | [U06](../upstream/U06-mlx-lm-gemma4-tool-parser-missing.md) | maintainer confirmed | closed, fixed |
| R2-11 | [U07](../upstream/U07-sglang-tool-choice-required-contaminates-args.md) | maintainer confirmed | open |
| R2-45 | [U08](../upstream/U08-sglang-harmony-commentary-channel-valueerror.md) | **maintainer reproduced** | closed, not fixed |
| R2-30 | [U09](../upstream/U09-vllm-mistral-chat-template-ignored.md) | maintainer confirmed | closed, fixed |
| R2-23 | [U10](../upstream/U10-vllm-vl-reranker-without-chat-template.md) | maintainer responded | closed, resolved as usage |
| R2-28 | [U11](../upstream/U11-glm-tool-content-array-renders-empty.md) | maintainer confirmed (the vendor) | closed, fixed |

**Already covered by a measured entry: 9.** Named, so they stop being
re-queued.

| Candidate | Covered by |
|---|---|
| R2-15 llama.cpp `--ctx-size` is total KV, `--parallel` divides it | trap [87](../traps/runtime/87-llamacpp-props-reports-per-slot-context.md), which measured `/props` reporting the per-slot figure |
| R2-16, R2-41 multi-slot non-determinism and shared system prompts | traps [91](../traps/runtime/91-concurrency-nondeterminism-has-a-prompt-length-floor.md) and [92](../traps/runtime/92-prompt-cache-is-a-second-divergence-source.md) |
| R2-17 clock in the system prompt kills the prefix cache | trap [93](../traps/template/93-clock-in-system-prompt-is-inert-and-the-mitigation-is-inverted.md), where it is refuted as worded |
| R2-18 `--cache-ram` and unified memory | trap [96](../traps/memory/96-list-devices-reports-host-memory-as-device-free-memory.md) |
| R2-46 partial GPU offload read as slowness | trap [97](../traps/runtime/97-partial-offload-is-invisible-in-log-and-props.md) |
| R2-13 SGLang hard-fails on a checkpoint with no chat template | trap [56](../traps/template/56-checkpoint-ships-no-chat-template.md). **The source also answers a blocker:** maintainer @zhaochenyang20 established the cause is not SGLang, `meta-llama/Llama-3.2-1B` and `-3B` lost `chat_template` remotely while the `-Instruct` siblings kept it, and `Meta-Llama-3.1-8B` too. See the note on OPEN_QUESTIONS below |
| R2-34 Llama3 tool calls inconsistent on SGLang | trap [19](../traps/tools/19-missing-jinja-breaks-tool-parsing.md). The thread's durable residue is a tool call arriving as `content` with `finish_reason: "stop"`; the rest was resolved as OpenAI-protocol interpretation across four maintainers, then closed by a staleness bot |
| R2-37 template revision drift | trap [25](../traps/template/25-empty-think-blocks-poison-prefix-cache.md), which **is** this issue, same reporter, same fix. The summary described it as revision drift; it is the empty-think-block cache defect. Worth knowing: maintainer @JJJYmmm reproduced it on llama.cpp with figures the entry does not carry (default template `cache_n = 0`, `prompt_n = 2115`; patched `cache_n = 1578`, `prompt_n = 570`) |

**Already settled by an earlier pass: 5.** R2-10 and R2-12 were refuted here
during the first-party SGLang bring-up, with a parser caveat; that session's
results are written and awaiting publication. R2-29 is
[refuted as worded and reframed](2026-07-28-r2-29-tool-calls-refuted-as-worded.md);
R2-31 [did not reproduce at small n](2026-07-27-r2-31-deepseek-v4-system-message-no-cliff-small-n.md);
R2-39 is [refuted on both stacks](2026-07-27-r2-39-thinking-plus-tools-not-reproduced-on-vllm.md).

**Still open as questions: 2.** R2-14 (SGLang NVFP4) remains inconclusive and
must not be cited either way; R2-27 (Mistral tokenizer-mode) remains
llama.cpp-inapplicable and open against vLLM. Both are in
[OPEN_QUESTIONS](OPEN_QUESTIONS.md).

## Closed as too weak: 22

Closing these is the point. A tier full of thin single-issue reports devalues
every entry beside it, and an un-closed candidate gets re-queued forever. Each
of these was read; none meets the bar of a maintainer confirmation or a clear
in-thread reproduction on a live claim.

**No citable primary source (11).** R2-09, R2-32, R2-35, R2-36, R2-50 rest on
X posts; R2-20, R2-21, R2-44 on Reddit threads; R2-19, R2-22 and R2-42 on
commercial blog posts. We could not read several of them at all, and the tier
requires a source that was read. A social post is a lead for a search, not
something to publish a claim from. If one of these is real, it will exist in a
tracker too.

**The mining pass itself found nothing (4).** R2-33 (Phi), R2-43
(text-generation-webui), R2-47 (MiniMax-M3) and R2-48 (AceReason) were filed
with "None dense this pass; thin coverage noted honestly", which was the right
call. They are coverage notes, not candidates, and they are now
[stack pages](../stacks/) or nothing. Closed as not-a-candidate.

**Source does not support the claim (2).** R2-24 and R2-49, which cite a
tracking index. R2-49's pooling-defaults question is a genuinely good one and
somebody should ask it; it just has no source yet.

**Documented behaviour, not a defect report (2).** R2-26 is sourced to vLLM's
own configuration documentation warning that skipping multimodal validation can
crash the engine. That is a documented consequence of a flag whose docs say it
is for trusted input. R2-25 closed with the behaviour explained by a
maintainer: `image_embeds` on the online server is gated behind
`--enable-mm-embeds` for two published security advisories, and the expected
shape is 2-D concatenated rather than stacked. Both fail loudly, which is the
opposite of what this registry collects.

**Retracted, superseded or unengaged (5).** R2-27's #19545 was retracted by its
own author. R2-08 is a client-library issue against LangChain, closed, and not
a serving-stack path. R2-38 is open with **zero comments** on a hosted cloud
service nobody outside the vendor can reproduce against. R2-40 was closed
`not planned` with no human comment at all, one report, no reproduction, no
engagement, which is the definition in
[CONTRIBUTING](../CONTRIBUTING.md#the-fourth-tier-upstream-reported) of what
this tier must not contain. R2-02's struck-through second bug is closed with
its parent.

## Two corrections this pass forced

**[The blocked-candidates note](2026-07-27-r2-blocked-not-testable.md) said
R2-23 was untestable for want of reranker weights, and gave a test plan for a
defect that is not there.** Corrected on that page. The trap that exists is
different and better, and it is published.

**[OPEN_QUESTIONS](OPEN_QUESTIONS.md) records the SGLang template-less
checkpoint question as blocked on naming an ungated checkpoint.** The primary
source names three (`meta-llama/Llama-3.2-1B`, `-3.2-3B` and
`Meta-Llama-3.1-8B`), but they are gated, so the blocker stands as stated. What the source *does*
settle is the mechanism: this is a model-repository property, and a chat
template can be **removed from a repo after release** without any weight
change. That is a sharper question than the one the queue was holding.

## Method, so this is repeatable

Every GitHub source was fetched through the API rather than read as a rendered
page, recording per issue: state and `state_reason`, the reporter, every
comment with its `author_association`, and the label set. Maintainer engagement
was then read off `author_association` in `OWNER`, `MEMBER` or `COLLABORATOR`.

**One caveat on that heuristic, because it bit.** `author_association` is not a
reliable maintainer test: in ollama#15539 the person who diagnosed and shipped
the fix is `CONTRIBUTOR`, and a mechanical read would have recorded that issue
as having no maintainer engagement. Every engagement label in the published
entries was set by reading the thread, with the association used only to sort
the reading order. A future pass should not automate this step.

**A second caveat, on corroboration.** Two threads carry near-identical
comments from one account asserting production confirmation from an agent
framework, with no version, no conditions and no counts. They are not counted
as independent reports, and the entry that could have cited them says so.
