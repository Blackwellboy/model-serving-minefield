# R2-29: tool calls as raw text on Nemotron NVFP4, refuted as worded and reframed

**Verdict: REFUTED AS WORDED, REFRAMED.** The symptom is not JSON and the path
to it is much narrower than the candidate described. This supersedes an earlier
internal draft written from one session alone, which had recorded a clean
refutation; with the second session merged in the disposition is neither
"reproduced" nor "refuted".

**Prior status:** NOT TESTABLE, no Nemotron weights on any lane, recorded
2026-07-27 in
[R2 blocked](2026-07-27-r2-blocked-not-testable.md). That block is now closed.

**Status of the evidence: measured here, raw not published.** The probe set is
archived on our side with its controls; it is not published, so the counts below
are ours to stand behind rather than yours to check. The reframed finding is
structural and you can check that half yourself: the call format is specified in
the checkpoint's own public chat template.

## The claim

Round-2 candidate: on Nemotron NVFP4, tool calls come back as **raw JSON in
`content`** instead of as structured `tool_calls`. The claim named the 120B
member of the family.

## What was tested

Two checkpoints, two serving versions, GB10-class single nodes:

- Nemotron 3 Nano 30B A3B NVFP4, vLLM 0.25.1
- Nemotron 3 Super 120B A12B NVFP4, vLLM 0.20.0 (**the member the claim named**)

Both with and without the card's documented parser pairing
(`--enable-auto-tool-choice` plus `--tool-call-parser qwen3_coder`).

## Result

**The claim as worded does not reproduce. What does reproduce is a
differently-shaped symptom on a narrower path.**

**1. Raw JSON: not observed anywhere.** With the card's parser pairing, both
lanes returned structured `tool_calls`, single and parallel (a two-city request
returned two calls), with reasoning on and off, and zero raw-text leakage. Saved
request and response pairs on both lanes.

**2. Without the parser flags, the request is rejected, not degraded.** vLLM
0.20.0 and 0.25.1 both reject any request carrying `tools` with **HTTP 400**:
`"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to
be set`. It fails loud. That guard is what makes the plain form of the claim
unreachable on this stack: you cannot silently get unparsed tool output from a
normal tools request against a server with no tool parser, because the request
never runs.

**3. Past the guard, the leakage is real and it is XML, not JSON.** The 120B
session reports that a request which gets past the 400 guard, for example with
`tool_choice: "none"`, against a server with no tool parser, returns the call as
raw **XML** inside `content` with `tool_calls` empty:

```
<tool_call>
<function=get_weather>
<parameter=city>
Paris
</parameter>
</function>
</tool_call>
```

This matches the template, whose own instruction block specifies a **nested XML**
call format, an inner `<function=...>` inside `<tool_call>` tags, and stresses
that no suffix may follow the call. A tool parser expecting flat JSON tool calls
parses nothing from it, silently.

**Evidence caveat - RESOLVED 2026-07-28, the hedge is withdrawn.** This
disposition's central factual claim is now archived rather than reported.

The caveat used to read: the archived no-parser probes on both lanes contained
**only the HTTP 400 arms**, with no saved request and response pair for the
`tool_choice: "none"` path anywhere in the evidence tree, so the XML result was
reported in the 120B session's deployment write-up and consistent with the
template, but **reported, not archived**.

It has since been reproduced and archived verbatim, with controls, as a saved
five-arm probe against the 120B lane:

| Arm | Request | HTTP | `tool_calls` | `<tool_call>` in `content` |
|---|---|---|---|---|
| A | `tools` + `tool_choice:"none"` | **200** | **`[]`** | **yes** |
| B | `tools` + `tool_choice:"auto"` | 400 | - | - |
| C | `tools`, `tool_choice` omitted | 400 | - | - |
| D | A + `enable_thinking:false` | 200 | `[]` | yes |
| E | **no `tools` at all**, same prompt | 200 | `[]` | **no** |

Arm E is the one that makes this a finding rather than an anecdote: with the
`tools` payload removed, the same prompt does **not** produce `<tool_call>`
markup. So the leak is attributable to the payload traversing an unparsed server,
not to the model's formatting habits. Arm D shows it is not a side effect of the
reasoning stream either.

The disposition below is unchanged - the evidence under it is simply this tree's
now.

## Suggested disposition

**REFUTED AS WORDED, REFRAMED.** The symptom is not JSON, and the path is
narrower than described.

The reframing, which is what a reader should carry away:

> On this family the tool-call format is **nested XML, not JSON**. A tool parser
> expecting flat JSON tool calls silently parses nothing. On vLLM the common case
> is protected by a hard HTTP 400 when the parser flags are missing, so the
> reachable path to raw text in `content` is a request that bypasses the guard,
> such as `tool_choice: "none"` against a server with no tool parser.

Keep open, scoped to:

- **non-vLLM stacks**, where there may be no equivalent guard and the plain claim
  may hold as stated
- **other reachable bypasses of the guard**, of which `tool_choice: "none"` was
  the one we found; there may be more

**Not** open for: vLLM with the card's parser pairing, on either checkpoint
tested. That case is clean and well evidenced, and the earlier draft's refutation
holds for it.

## Correction to the earlier draft

The earlier draft said "refuted-here for vLLM plus the 30B member; keep open
scoped to the 120B member specifically". The 120B member has since been tested,
so that scoping is closed: the parser pairing works there too. What replaces it is
the format correction (XML, not JSON) and the narrower reachable path, neither of
which the earlier draft had.

## Cross-references

The XML-versus-JSON format point is a tools-category finding and is held here
rather than promoted, because the reachable path is narrow enough that the
honest entry would be mostly caveat. If anyone hits it on a stack with no
equivalent HTTP 400 guard, that is the missing piece and it promotes.

Related entries: [trap 19](../traps/tools/19-missing-jinja-breaks-tool-parsing.md)
for what a missing parser costs generally, and
[trap 26](../traps/tools/26-tool-call-inside-unclosed-think.md) for the other way
a well-formed call gets eaten.

Tested 2026-07-27 and 2026-07-28. Merged and re-adjudicated 2026-07-28.
