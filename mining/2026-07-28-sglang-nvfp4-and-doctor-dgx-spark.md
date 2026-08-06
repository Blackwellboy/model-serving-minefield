# Q7 and Q8: SGLang NVFP4 generation and doctor portability on DGX Spark

**Verdict: Q7 REFUTED under its pre-registered first-generation criterion; Q8
CONFIRMED, with one stack-identification defect fixed.** Both pinned NVFP4
checkpoints reached generation on SGLang 0.5.16 on a DGX Spark. The non-Laguna
control returned the requested answer exactly. Laguna returned a correct first
token on the completion route, which meets Q7's recorded REFUTE bar, but its
longer output was not healthy. This is not a quality or production-support
claim.

**Status: contributor-measured, conditions as reported.** Measured by
[@newageinvestments25-byte](https://github.com/newageinvestments25-byte) on his
own hardware. The maintainers have not reproduced these conditions. Request,
response, doctor JSON, package-install and full server logs are held outside
this tree; the exact public revisions, commands, response excerpts and bounded
claims are recorded below.

## The pre-registered bars

The criteria below were copied from
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) before either arm ran.

- **Q7 CONFIRM:** Laguna NVFP4 fails to generate on SGLang while an equivalent
  non-Laguna NVFP4 checkpoint succeeds.
- **Q7 REFUTE:** Laguna NVFP4 generates.
- **Q8 CONFIRM:** the doctor runs and its verdicts are meaningful on SGLang.
- **Q8 REFUTE:** probes break or return misleading verdicts.

## Unit under test

| Surface | Pinned condition |
|---|---|
| Hardware | NVIDIA DGX Spark, GB10, aarch64, compute capability 12.1, 121 GiB unified memory |
| Driver / CUDA | driver 580.173.02; torch CUDA 13.0 |
| Python / SGLang | Python 3.12; `sglang==0.5.16` |
| Kernels | `sglang-kernel==0.4.5`, `flashinfer-python==0.6.14`, `triton==3.6.0` |
| Torch / transformers | `torch==2.11.0`, `transformers==5.12.1` |
| Control | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4` at `ce1b7c1a03e2331946c30ac50d56262a14516f8b` |
| Target | `poolside/Laguna-S-2.1-NVFP4` at `07614121b31898586430f189d27a25a0be310843` |
| Shared serve settings | loopback only, context 32768, static memory fraction 0.75, FlashInfer attention and sampling backends |
| Model-specific parser pairing | Nemotron: `nemotron_3` reasoning and `qwen3_coder` tools; Laguna: `poolside_v1` for both |

The torch wheel advertised `sm_120` but not `sm_121`. That did not prevent the
FlashInfer autotune cache from selecting an `sm121` key or either arm from
reaching generation.

## Bring-up conditions that mattered

The installed dependency set differed from the earlier packaging-only note in
two material ways.

1. SGLang 0.5.16 declared `sglang-kernel==0.4.5`. Installing the older
   `sgl-kernel==0.3.21` beside it overlapped the same import tree, so the older
   distribution was removed and 0.4.5 was reinstalled before either measured
   arm.
2. The default JIT DeepGEMM import failed before model load with
   `ModuleNotFoundError: deep_gemm.utils.layout`. Both measured arms therefore
   used `SGLANG_ENABLE_JIT_DEEPGEMM=0`. This was held constant. It does not hide
   the selected NVFP4 MoE paths reported below.
3. A transient service must include the virtual environment's `bin` directory
   in `PATH`; without it FlashInfer JIT failed because `ninja` was not found.
   That failed launch was discarded before the measured control arm.

The effective serve shape was:

```bash
SGLANG_ENABLE_JIT_DEEPGEMM=0 \
PATH="VENV/bin:$PATH" \
VENV/bin/python -m sglang.launch_server \
  --model-path MODEL_PATH \
  --host HOST --port PORT \
  --trust-remote-code \
  --context-length 32768 \
  --mem-fraction-static 0.75 \
  --reasoning-parser REASONING_PARSER \
  --tool-call-parser TOOL_CALL_PARSER
```

The CUDA and TorchInductor caches were separated by arm. SGLang's own
FlashInfer autotune cache remained in its default common root, keyed by its
model/configuration hash. Startup timings are therefore descriptive only and
are not compared as performance results.

## Q7 result

The non-Laguna control ran first.

| Arm | Runtime selection | Generation observation |
|---|---|---|
| Nemotron control | `ModelOptNvFp4FusedMoEMethod`; `quant=modelopt_fp4`; `quant_algo=NVFP4`; FlashInfer autotune on `sm121` completed | Chat completion returned HTTP 200, `finish_reason=stop`, `content="CONTROL_OK"`, 7 completion tokens |
| Laguna target | `CompressedTensorsW4A4Nvfp4MoE`; `quant=compressed-tensors`; `LagunaForCausalLM` loaded | Completion request `2+2=` returned HTTP 200 and began `4</think>`, then continued to the 32-token ceiling |

The control establishes that this SGLang/GB10 lane can load and decode a
non-Laguna NVFP4 checkpoint. Laguna then loaded 15 shards, allocated its KV
cache, completed CUDA graph capture and generated a correct first token. Under
the criterion written before the run, that **REFUTES Q7**.

That result is deliberately narrow. Laguna's chat-completion output was often
incoherent, and SGLang emitted a transformers warning that this tokenizer has
an incorrect Mistral regex and should be loaded with
`fix_mistral_regex=True`. Explicit thinking-on, thinking-off and absent-kwarg
arms all returned non-empty but degraded text; the absent arm also exposed an
orphan `</think>`. No controlled fix was run, so this note does not attribute
the degraded output to the tokenizer warning, quantisation, parser pairing or
another layer. It proves architecture bring-up and decode, not correctness.

## Q8 result

The pinned doctor from the tested repository commit ran to completion against
both warm SGLang endpoints with `--json`, `--report`, `--hf-repo` and immutable
`--hf-revision` values. Each run made 14 completion requests.

| Arm | Doctor coverage line | Manually checked numbered findings |
|---|---|---|
| Nemotron | `implemented 19/103 | executed on this stack 11 | clean 9 | problems 1 | inconclusive 9 | not implemented 84` | Trap 77 fired: the paired baseline returned 200 and an invented top-level field was also accepted with 200. The exact control generation independently confirmed the requested thinking-off behavior rather than trusting acceptance. |
| Laguna | `implemented 19/103 | executed on this stack 8 | clean 5 | problems 3 | inconclusive 10 | not implemented 84` | Trap 77 reproduced as above. Trap 12 fired on HTTP 200, `finish_reason=length`, empty content and 569 reasoning characters at the 512-token cap. Trap 02 fired only on the absent-kwarg arm, which started with an orphan `</think>`; explicit arms did not. |

Those observations match the saved response shapes. Inconclusive results stayed
inconclusive, including the one-sample thinking-toggle map and the checkpoint's
quantisation label without a runtime comparison. The doctor therefore produced
meaningful, bounded verdicts rather than treating a successful process as a
bill of health. **Q8 is CONFIRMED.**

One reporting defect was real but did not invalidate the verdicts: SGLang
0.5.16 has neither `/props` nor `/version`, so the doctor printed
`openai-compatible (vLLM/MLX/other)` even though `/v1/models` returned
`owned_by: "sglang"`. The accompanying patch recognises that exact public
response shape and adds SGLang to the stacks whose
`chat_template_kwargs.enable_thinking` control has been established. Its
regression failed before the code change and passes after it.

## Disposition

- Close Q7 as **REFUTED under the pre-registered generation criterion**.
- Close Q8 as **CONFIRMED**, while landing the tested stack-identification fix.
- Add SGLang as a contributor-measured surface to existing traps 02, 12 and 77.
- Keep output quality, the Mistral regex warning and the exact Laguna corruption
  mechanism open. This run did not isolate any of them.

The pre-existing services were stopped for an exclusive lane, then restored.
Both previously healthy text endpoints completed their original baseline
probe after restoration, and the image service answered its queue probe. A
fourth model service returned to its pre-existing no-endpoint startup state;
that condition predates this experiment and is not claimed as healthy here.
