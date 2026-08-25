# Trap 127: a whole-file bind mount shadows a module inside the image, and an unattended image update turns that into a crash-loop outage

**Found by @sethforprivacy.**

**Status: contributor-measured, conditions as reported.** Measured on the
finder's private 2x DGX Spark (GB10) production lane on 2026-08-19.
Blackwellboy has not independently reproduced this lane. Conditions and
counts in full below; the raw router and container logs are in the finder's
private deployment and are not published.

**Symptom.** An inference gateway behind a reverse proxy answers 502 for hours
while the model backends behind it are healthy and idle. The container's
restart count climbs steadily. Every start dies at import with an
`ImportError: cannot import name 'SomeClass'` from a module you thought you
knew, and nothing in your compose file changed: only the image tag moved,
pulled by an unattended updater, at 04:05 in the morning. The reverse proxy
has no healthy backend, so it answers 502 for the entire window.

**Mechanism.** The compose file bind-mounts a host file over a module path
inside the image (`./patches/foo.py:/opt/venv/.../foo.py:ro`). The mount
replaces the whole stock file, so the container runs a mix: your mounted
module plus every other module from whatever image tag is current. That mix
is silently coupled to one upstream revision. When an unattended updater
pulls a newer image whose other modules import a symbol the mounted file
predates, every start dies at import, before any request can be served. With
`restart: unless-stopped` the failure becomes a crash loop, and the reverse
proxy, seeing no healthy backend, answers 502. Nothing in the compose diff
changed; the image did.

**Stacks and builds bitten.** lmstack router (`lmcache/lmstack-router:latest`,
image built 2026-08-18T19:40Z) fronting vLLM on a 2x DGX Spark (GB10) lane,
docker compose whole-file `:ro` bind mount, watchtower unattended nightly
updates monitoring every container by default. Measured: 4 h 22 m of 502
(04:05Z to 08:27Z), **241 container restarts**, both model clusters healthy
and idle throughout, zero requests lost because none reached them. The
mounted module predated `PriorityRouter`, a class the newer image's stock
module imports at module scope. A throwaway-container reproduction of the
pre-rebase patch failed with the same ImportError the live container hit;
the rebased patch passed and the live service came back healthy, so the
failure was pinned to the mount/image pair, not to the config or the model.

**The check.**

1. Audit every compose mount that targets a *file* inside the image, not a
   directory the image expects to be filled from outside: `docker compose
   config` and look for `:ro` entries whose source is a flat file and whose
   target sits inside the installed package tree.
2. Before updating the image of any such container, extract the mounted
   module from the NEW image and diff it against the mounted file, then
   test-import the mounted file in a throwaway container with the new image.
   Do this before the live container is touched.
3. Alert on container restart count. A crash loop writes itself in restart
   counts and no TCP health probe can see it.

**The fix.** Stop feeding the container's own modules from outside the image
where you can: subclass and register, or upstream the delta so the mount
disappears entirely. Where a whole-file mount must exist, take that container
off unattended updates and drive it with a gated script that pulls, diffs the
operator delta against the new image's stock module, test-imports in a
throwaway container, and restores the known-good image if the live one does
not come up. When a crash loop does appear, check the image pull time before
reading the last error line: an `ImportError` naming a symbol your
configuration does not reference is the signature of the shadowing mount.

**Found.** 2026-08-19, when the unattended nightly update pulled the new
router image and the service crash-looped for 4 h 22 m.

**Attribution.** @sethforprivacy. Raw router logs and the incident writeup are
in the finder's private deployment and were not published.

**Related.** [104](104-stale-launch-script-silently-reverts-config.md), [53](../runtime/53-config-edit-never-took-effect.md), [09](../runtime/09-image-choice-changes-outcome.md), [75](75-release-asset-renamed-pinned-url-404.md).
