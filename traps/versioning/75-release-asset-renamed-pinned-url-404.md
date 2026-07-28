# Trap 75: the release asset was renamed, so every pinned install URL is a silent 404

**Found by Blackwellboy.**

**Status: reproduced here**, 2026-07-28, on Ollama 0.32.5. The evidence is a
public URL: fetch the old asset name from the vendor download path or the
GitHub release and read the status code. Nothing here needs anything from us,
and nothing here depends on our hardware.

**Symptom.** An install step that has worked for months starts failing with

```
curl: (22) The requested URL returned error: 404
```

against a URL nobody changed. The version in the URL is still a real version.
The host is up. Everything about the failure points at a network problem or a
withdrawn release, and it is neither: the **asset name** changed, not the
version and not the location.

**Mechanism.** The project changed its release archive format. What used to be

```
ollama-linux-<arch>.tgz
```

is now

```
ollama-linux-<arch>.tar.zst
```

Both the vendor download path and the GitHub release asset return **404** for
the old name. There is no redirect and no deprecation window, because from the
publisher's side nothing was removed: a differently-named artifact was added
and the old one stopped being produced.

Two consequences that are worse than the 404 itself:

1. **Extraction gains a hard dependency.** `tar -xzf` will not open a zstd
   archive. You need `zstd` present, and the installer's own remedy for a
   missing `zstd` requires root, which is exactly the thing an unattended
   install in a container or a CI job usually does not have at that point.
2. **It breaks automation and not interactive use.** A person installing by
   hand follows the current instructions and never sees this. The failure is
   concentrated in pinned scripts, Dockerfiles and provisioning roles, which
   is where a 404 is least likely to be read by anybody the same day.

**Stacks and builds bitten.** Ollama at some version at or before 0.32.5;
observed at 0.32.5 on aarch64. The class is not Ollama-specific: any project
that changes archive format without preserving the old asset name does this.

**The check.** Two lines, and they cost nothing:

```bash
# assert the asset you pin actually exists, before you depend on it
curl -sfI "$ASSET_URL" >/dev/null || { echo "asset URL is dead: $ASSET_URL"; exit 1; }
command -v zstd >/dev/null || echo "warning: this archive format needs zstd"
```

The general form of the rule: **a pinned URL is a claim about the remote, so
assert it.** `curl -f` turns a 404 into a non-zero exit instead of a
zero-byte file that the next command fails on for an unrelated-looking reason.

**The fix.** Switch to `.tar.zst` and extract with `tar --zstd -xf`, and make
`zstd` a declared prerequisite of the install rather than something the
installer tries to acquire at the point of failure. If you must survive both
formats, select on what the release actually offers rather than on the version
number, because the version number is not what changed.

**Found.** 2026-07-28, during the first Ollama bring-up in this registry's
coverage.

**Attribution.** Blackwellboy. This is the registry's first Ollama entry;
Ollama was named in [CONTRIBUTING](../../CONTRIBUTING.md#where-coverage-is-thin)
as a stack with no entries at all.
