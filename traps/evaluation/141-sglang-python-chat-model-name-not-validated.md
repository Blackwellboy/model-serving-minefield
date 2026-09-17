# Trap 141: SGLang Python chat can answer a request naming a model it does not serve

**Found by @scottleimroth.**

**Status: contributor-measured, conditions as reported.** The contributor reproduced the behavior on SGLang build `0.0.0.dev1+g5f55db35e` with two separate NVFP4 serves on DGX Spark / GB10. Maintainer source adjudication also found the identity check absent from the affected current Python OpenAI chat path while sibling SGLang API paths do validate model identity.

**Symptom.** A health check, benchmark, router or canary sends an OpenAI-compatible chat request naming model B to a server that is actually serving model A. Instead of rejecting the mismatch, the Python SGLang chat route can return HTTP 200 and ordinary assistant content from the model that is actually loaded.

The dangerous part is not merely an ignored optional knob. `model` is the field a client normally uses to say which model it believes it is measuring. A plausible response therefore looks like identity proof even when it is only proof that *some* model answered.

**Mechanism.** On the affected Python OpenAI chat path, request validation does not establish that `request.model` equals the served base-model identity before request conversion. The model string is still available to downstream request/LoRA resolution and response metadata, so accepting the request does not prove that the named base model is resident.

Current SGLang has an important route split. The Rust OpenAI chat/completions path rejects a request model that differs from the served model, and the newer `/v1/responses` implementation has explicit known-model validation. This entry therefore does **not** describe every SGLang API surface.

**Stacks and builds bitten.** Contributor runtime evidence: SGLang `0.0.0.dev1+g5f55db35e`, Python OpenAI-compatible chat path, two separate Qwen3.8-family NVFP4 serves on NVIDIA DGX Spark / GB10. Current-source adjudication supports the same validation asymmetry on the Python chat route. A vLLM serve used by the contributor rejected the same negative-control shape correctly.

**The check.** First establish resolved server identity independently of the client request, for example from the server's own model listing/info or resolved launch state. Then send a chat request whose `model` value is deliberately not one of the served model names.

**TRAP PRESENT:** the server returns ordinary HTTP-200 assistant content for the deliberately wrong model name.

**TRAP ABSENT:** the route rejects the mismatched model name before generation, while a correctly named control request succeeds.

Do not treat `{"model": "X"}` followed by HTTP 200 as evidence that X produced the answer. Identity assertions must compare the client's requested name with resolved server state.

**The fix.** Validate the requested base-model identity on the affected route before generation, consistently with sibling API paths that already enforce known/served model names. Until that contract is enforced by the server, harnesses and canaries should query resolved server identity and fail closed on a mismatch instead of trusting the request field they themselves supplied.

**Claim boundary.** May claim that the contributor reproduced wrong-name acceptance on the pinned SGLang Python chat lane and that current-source adjudication found the same model-identity validation gap on that route. Must not claim that SGLang's Rust OpenAI path or `/v1/responses` has the same behavior, or that every SGLang release is affected. This is related to but distinct from Trap 77: Trap 77 covers invented/unrecognized request fields being accepted; this trap concerns the standard `model` identity field itself.

**Attribution.** Finding and runtime reproduction: **@scottleimroth**. Maintainer source adjudication and registry framing: Blackwellboy. Public report: [issue #71](https://github.com/Blackwellboy/model-serving-minefield/issues/71).

**Related.** [Trap 77](../reasoning/77-only-one-request-field-is-validated.md) covers accepted invented request fields rather than served-model identity.
