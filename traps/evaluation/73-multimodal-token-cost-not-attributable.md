# Trap 73: multimodal token cost cannot be read out of the usage block

**Found by Blackwellboy.**

**Status: measured here, raw not published.** Seven input classes against a
common text baseline, on one lane. The per-request usage blocks are not
published, so a stranger cannot check these counts; the procedure below
re-derives them on their own lane in a few minutes, which is the cheaper
route and the one to take.

**Symptom.** You want to know what an image costs you, or whether your prefix
cache is working. The usage block has a field for exactly that and it is null on
every response.

**Mechanism.** `prompt_tokens_details` is `null` on every single response, with
and without media. Only the aggregate `prompt_tokens` moves. There is therefore
no supported way to separate image, audio, video and text cost, or to see cache
hits, from the API.

The workaround is differencing against a text-only control, which is what these
numbers are. Same question in every case, 23-token text baseline:

| Input | Added prompt tokens |
|---|---|
| image 64 x 64 | 259 |
| image 800 x 600 | 478 |
| image 1024 x 768 | 771 |
| image 5000 x 5000 | 3309 |
| audio, 2 seconds | 28 |
| audio, 3.5 seconds | 50 |
| video, 8 seconds at 640 x 480 | 2247 |

Three things fall out that are worth knowing before you budget anything. **The
smallest possible image still costs about 256 tokens**, so there is a floor and
downscaling below it buys nothing. **The largest lands close to the ceiling the
preprocessor config implies**, twelve tiles plus a thumbnail at 256 tokens each.
**Audio runs at roughly fifteen tokens per second** and **video is by far the most
expensive input per second of material**.

**Stacks and builds bitten.** NVIDIA Nemotron 3 Nano Omni 30B A3B Reasoning
NVFP4, vLLM 0.20.0 upstream arm64 container, single GB10-class node.

**The check.** Send one request with no media and one with your typical media,
same text, and look at `prompt_tokens_details`. If it is null on both, you are
differencing from now on. The registry doctor now reports this on any lane that
accepts an image part.

**The fix.** There is nothing to fix server-side. What to do instead:

1. **Build a small differencing table for your own media profile** before you
   budget context or cost. The numbers above are this preprocessor's, at these
   dimensions; yours will differ.
2. **Do not claim a cache hit rate you cannot observe.** With
   `prompt_tokens_details` null there is no cache visibility at all from the API,
   so any statement about prefix-cache effectiveness on this lane is inferred
   from latency, and latency has other explanations.
3. **Account for the image floor.** If your pipeline resizes images down to save
   tokens, verify it actually saves any; below the tile floor it does not.

**If you miss it.** You budget context for a workload whose media cost you
guessed, and you attribute latency changes to a cache you cannot see.

**Negatives recorded.**

- `prompt_tokens_details` is null on text-only requests too, so this is not
  media-specific plumbing that failed; the field is simply never populated.
- The aggregate `prompt_tokens` is accurate and moves as expected, so differencing
  is a sound workaround, just a manual one.

**Related.**
[trap 13](../memory/13-utilization-fraction-on-unified-memory.md), the other
entry about a resource number that does not mean what its name suggests.

**Found.** 2026-07-27.

**Attribution.** Blackwellboy.
