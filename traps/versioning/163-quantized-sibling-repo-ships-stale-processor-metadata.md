# Trap 163: the quantized sibling repo still ships processor metadata the base repo has already replaced

**Found by Blackwellboy.**

**Status: reproduced here** (runnable procedure in The check, against the two
public Hugging Face repositories at pinned revisions; it needs no GPU and
downloads only small JSON files).

**Symptom.** You serve the official quantized build of a vision-language
model on a current engine, and startup fails before any weights matter.
First:

```
ValueError: The repository <model dir> contains custom code which must be
executed to correctly load the model. ... Please pass the argument
`trust_remote_code=True` to allow custom code to be run.
```

The base (unquantized) model from the same publisher, on the same engine
build, needs no such flag. If you remove the `auto_map` entries to get past
that, the next failure is:

```
ValueError: Unrecognized image processor in <model dir>. Should have a
`image_processor_type` key in its preprocessor_config.json of config.json ...
```

even though `preprocessor_config.json` does carry an `image_processor_type`
key.

**Mechanism.** The base repository and its quantized sibling are separate
repositories, versioned separately. On 2026-10-13 the base repository moved
its processor to the classes that ship natively in transformers: its
`processor_config.json` became `{}`, its `preprocessor_config.json` lost the
class and `auto_map` keys, and its `tokenizer_config.json` dropped `auto_map`
and `processor_class`. The AWQ repository, last modified a day earlier, still
carries the previous metadata:

- `auto_map` entries in `processor_config.json`, `preprocessor_config.json`
  and `tokenizer_config.json` pointing at `processing_minicpmv4_7.py`,
  `image_processing_minicpmv4_7.py` and `video_processing_minicpmv4_7.py`.
  **None of those three files is in the AWQ repository.** The engine sees
  `auto_map`, concludes custom code is required, and refuses without
  `--trust-remote-code`. Passing the flag cannot help: there is no module to
  load.
- `image_processor_type: MiniCPMV4_7ImageProcessor`, a class name that exists
  only in that absent remote code. transformers 5.19.0 has no such class, so
  with `auto_map` gone the lookup fails as "unrecognized".

Nothing about the weights is wrong. The quantized repository simply froze a
snapshot of auxiliary metadata that the base repository has since migrated
away from, and the engine's model support was written against the new one.

**Stacks and builds bitten.** `openbmb/MiniCPM-V-4.7-35B-A3B-AWQ` at
`ea491d008227809c62ff72dce9a5650d5d0576c1` against base
`openbmb/MiniCPM-V-4.7-35B-A3B` at `17e651151c161dce119cd0ac57570f60da8a0b40`.
vLLM `0.31.1rc1.dev371+gdf6c7ad03` (nightly), transformers 5.19.0, one RTX
5090. Both failures above were captured on that build, in that order. We did
not launch with `--trust-remote-code`, for the reason the check makes
visible: the code it would run is not there, and accepting remote-code
execution to work around missing files would run whatever appears at that
path later.

**The check.** Compare the module names that `auto_map` references against the
files the repository actually contains, for the quantized repo and its base.
Standard library only:

```python
import json, urllib.request
HF = "https://huggingface.co"
REPOS = {
    "awq":  ("openbmb/MiniCPM-V-4.7-35B-A3B-AWQ",
             "ea491d008227809c62ff72dce9a5650d5d0576c1"),  # pragma: allowlist secret  (public Hugging Face revision SHA)
    "base": ("openbmb/MiniCPM-V-4.7-35B-A3B",
             "17e651151c161dce119cd0ac57570f60da8a0b40"),  # pragma: allowlist secret  (public Hugging Face revision SHA)
}
CONFIGS = ("processor_config.json", "preprocessor_config.json",
           "tokenizer_config.json", "config.json")

def get(url):
    return urllib.request.urlopen(url, timeout=60).read()

def automap_modules(obj):
    found = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "auto_map" and isinstance(v, dict):
                for target in v.values():
                    for t in (target if isinstance(target, list) else [target]):
                        if isinstance(t, str) and "." in t:
                            found.add(t.split("--")[-1].rsplit(".", 1)[0] + ".py")
            else:
                found |= automap_modules(v)
    return found

for name, (repo, rev) in REPOS.items():
    files = {s["rfilename"] for s in json.loads(
        get(f"{HF}/api/models/{repo}/revision/{rev}"))["siblings"]}
    wanted = set()
    for cfg in CONFIGS:
        if cfg in files:
            wanted |= automap_modules(json.loads(get(f"{HF}/{repo}/resolve/{rev}/{cfg}")))
    missing = sorted(wanted - files)
    print(f"{name}: auto_map references {sorted(wanted)}; missing from repo {missing}")
```

Recorded 2026-10-13:

| Repository | Modules referenced by `auto_map` | Present in the repository |
|---|---|---|
| AWQ, `ea491d0` | `processing_minicpmv4_7.py`, `image_processing_minicpmv4_7.py`, `video_processing_minicpmv4_7.py` | none of the three |
| base, `17e6511` | none | not applicable |

The trap is present whenever a referenced module is missing. Run the same
check on any quantized, abliterated or otherwise re-uploaded sibling before
you serve it, against the base revision your engine's model support targets.

**The fix.** Take the processor metadata from the base repository and keep the
weights from the quantized one. Concretely: a directory that links every AWQ
file, and replaces `processor_config.json`, `preprocessor_config.json` and
`tokenizer_config.json` with the base repository's copies at the pinned base
revision. Before doing that, confirm the files you are **not** replacing agree:
at these revisions `chat_template.jinja` and `tokenizer.json` are
byte-identical between the two repositories, and `generation_config.json`
differs only in its `transformers_version` field. With that overlay the same
engine build started cleanly, served text and tool calls, and passed a
five-item vision smoke test (OCR, colour, position, counting, chart reading)
5/5 with thinking off.

Do not reach for `--trust-remote-code` here. Pin both revisions, and re-run the
check whenever either repository moves, because the quantized repository may
be updated to match and the overlay then becomes unnecessary.

**Found.** 2026-10-13, bringing up MiniCPM-V 4.7 on a nightly vLLM build the
same day the base repository's processor migration landed.

**Attribution.** Blackwellboy. Related:
[trap 14](14-finetune-reupload-not-drop-in.md) (a re-upload is a separate
repository, not a drop-in),
[trap 56](../template/56-checkpoint-ships-no-chat-template.md) (another case
where the checkpoint's own metadata decides what the server loads), and
[trap 103](../template/103-torchvision-abi-mismatch-blocks-autoprocessor.md)
(a different way for processor loading to fail after the weights are fine).
