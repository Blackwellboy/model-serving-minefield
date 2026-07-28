# Trap 72: a caller's bad media path is reported as a server fault

**Found by Blackwellboy.**

**Status: reproduced here across fourteen cells covering both transports and six
malformation classes.**

**Symptom.** Your retry logic hammers a lane forever. Your alerting pages on
server errors from a lane that is healthy. The requests that fail are always the
ones with a media path in them.

**Mechanism.** The same class of caller error is classified two different ways
depending on transport. Malformed media sent **inline** is correctly a 4xx.
Media referenced by a **path or URL** that cannot be fetched is a **500**.

| Condition | Status | Body |
|---|---|---|
| truncated image, inline | 400 | `Failed to load image: image file is truncated` |
| zero-byte image, inline | 400 | `cannot identify image file` |
| text file with an image extension, inline | 400 | `cannot identify image file` |
| corrupt base64, inline | 400 | `cannot identify image file` |
| audio bytes sent as an image, inline | 400 | `cannot identify image file` |
| more media than the per-prompt limit | 400 | `At most 1 image(s) may be provided in one prompt.` |
| unknown content part type | 501 | `Unknown part type: hologram_url` |
| **local media path does not exist** | **500** | `[Errno 2] No such file or directory` |
| **remote media host unreachable** | **500** | `Cannot connect to host ...` |

The inline column is exemplary: specific, actionable, correctly classified. The
path column is not, and the difference is invisible to a caller who only ever
uses one transport.

**Why 5xx is the damaging classification.** Every standard retry policy treats
5xx as transient and 4xx as permanent, which is the right default. So a
permanently missing file gets retried until a budget runs out, and a dead remote
host gets retried at whatever rate your backoff allows, indefinitely. Meanwhile
your dashboards attribute a client mistake to the server, so the on-call response
is to investigate a healthy lane.

**Stacks and builds bitten.** NVIDIA Nemotron 3 Nano Omni 30B A3B Reasoning
NVFP4, vLLM 0.20.0 upstream arm64 container, single GB10-class node.

Worth recording how this was found: a driver bug in the session's own harness
sent host-side paths to a server that resolves paths inside its container. That
mistake is the exact shape a real deployment makes, and the 500 it produced is
what surfaced the defect.

**The check.** One request with a media reference to a path that does not exist.
If the status is 5xx, you have it. The registry doctor now runs this on any lane
that accepts an image part.

**The fix.** Client-side, because the classification is the server's:

1. **Resolve and validate media before the request.** Stat local files, and
   prefer inline transport where size allows, because the inline path classifies
   correctly.
2. **Do not retry on 5xx from a media-carrying request** without first checking
   whether the media resolves. Treat "5xx and the request had a path reference"
   as a caller-error candidate.
3. **Route media-fetch failures away from server alerting.** They are your
   errors, and they will otherwise drown the signal from real server faults.
4. Remember that paths are resolved **inside the server's filesystem namespace**,
   not yours. A containerised lane and a host-side client do not share a view,
   and the error you get for that mistake is a 500.

**Negatives recorded.**

- Every inline malformation class is correctly 4xx with a specific message. This
  is not a general error-handling weakness; it is one path.
- The per-prompt media limit produces a clean, specific 400 naming the limit.
- An unknown content-part type is a 501, which is defensible.

**Related.**
[trap 16](../evaluation/16-finish-reason-is-not-a-failure-signal.md), the
neighbouring "the status field is not telling you what you think" entry.

**Found.** 2026-07-27.

**Attribution.** Blackwellboy.
