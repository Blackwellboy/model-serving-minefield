# Optional bounded execution API

`run_checks(plan, execution=ExecutionControl(...))` is additive. Without an
execution context the existing generation-budget behavior remains unchanged.
The context covers raw GET/POST, discovery, chat/legacy completions and SSE.
It rejects redirects, environment proxies, undeclared paths/origins, excessive
output requests and response sizes, and checks a monotonic deadline/cancellation.
There are no transparent retries. A context is one-use and thread/context-local.

`preview_requests(plan)` currently supports only request_validation with an
explicit model. It returns conditional discovery requests plus both synthetic
POST bodies, shared with the probe implementation. Other probes fail closed as
UNSUPPORTED_REQUEST_PREVIEW. Pass the request list to ExecutionControl to bind
exact ordered bytes semantically; conditional branches may skip entries only.

Cancellation checks before requests and bounded reads. An in-flight blocking read
may last until the configured socket timeout; remote compute termination is
unknown. No callback should do expensive I/O. Results retain partial probe runs
and add all-HTTP and wire-generation usage. Discovery counts are separate from
per-probe counts. Core does not grant user approval or coordinate endpoint locks.

Validation: new execution tests and existing API phase-zero tests passed (14 at
initial checkpoint); adapter actual-wire/grant/cancellation service tests passed.
The broad Windows fixture run has failures also reproducible on the unmodified
baseline; investigation is ongoing. This branch is not release-qualified.
