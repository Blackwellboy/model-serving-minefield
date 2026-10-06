"""Offline detectors behind `minefield scan`: each rule fires on its own
signature and stays quiet on a matched safe control."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from minefield.coverage import build_coverage
from minefield.log_inspector import inspect_logs
from minefield.model_inspector import inspect_model_folder
from minefield.registry import load_registry
from minefield.results_inspector import inspect_results
from minefield.scan import scan
from minefield.static_inspector import inspect_files
from minefield.template_inspector import inspect_template

ROOT = Path(__file__).resolve().parents[1]
QWEN_TEMPLATE = ROOT / "checks" / "fixtures" / "qwen38_nvfp4_52d1adc" / "chat_template.jinja"


def _ids(report):
    return {f["trap_id"] for f in report["findings"]}


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name: str, text: str) -> Path:
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


RISKY_LAUNCH = """\
vllm serve Qwen/Qwen3.8 --gpu-memory-utilization 0.95 --speculative-config '{"method": "qwen3_next_mtp", "num_speculative_tokens": 3}' --compilation-config '{"fuse_gemm_comms": true, "max_cudagraph_capture_size": 64}'
llama-server -m m.gguf -ngl 40 -fa off -ctk q8_0 -ctv q4_0
python -m mlx_lm.server --model x --max-tokens 1024
export NCCL_IB_GID_INDEX=3
ray start --head --include-log-monitor=false
docker run -v /models/qwen:/models vllm/vllm-openai
BASE_URL=http://spark.local:8000/v1
llama-server --override-kv qwen3moe.expert_used_count=int:16
vllm serve x --speculative-config '{"method": "ngram", "num_speculative_tokens": 4}'
"""
SAFE_LAUNCH = """\
vllm serve Qwen/Qwen3.8 --gpu-memory-utilization 0.95 --kv-cache-memory-bytes 12884901888 --max-num-seqs 4 --speculative-config '{"method": "mtp"}' --enforce-eager
llama-server -m m.gguf -ngl 99 -fa on -ctk q8_0 -ctv q8_0
docker run --mount type=bind,source=/models,target=/models vllm/vllm-openai
BASE_URL=http://192.168.1.20:8000/v1
"""
NEW_CONFIG_TRAPS = {"13", "18", "32", "33", "45", "48", "97", "98", "114", "117", "118", "122", "130", "138", "142"}


class ConfigRules(TempDirCase):
    def test_each_new_rule_fires_on_its_signature(self):
        found = _ids(inspect_files([str(self.write("risky.sh", RISKY_LAUNCH))]))
        self.assertEqual(NEW_CONFIG_TRAPS - found, set())

    def test_safe_launch_fires_nothing(self):
        self.assertEqual(_ids(inspect_files([str(self.write("safe.sh", SAFE_LAUNCH))])), set())

    def test_repeated_static_signature_is_bounded_and_reported(self):
        path = self.write("repeat.sh", ("reasoning_effort=x\n" * 100))
        report = inspect_files([str(path)])
        self.assertEqual(len(report["findings"]), 8)
        self.assertIn(
            {"code": "RULE_MATCH_LIMIT", "file": str(path.resolve()), "trap_id": "07", "limit": 8},
            report["truncations"],
        )

    def test_whole_file_mount_over_a_package_module(self):
        compose = self.write("compose.yml", "services:\n  gw:\n    volumes:\n"
                             "      - ./patched.py:/usr/lib/python3.12/site-packages/pkg/mod.py:ro\n")
        self.assertIn("127", _ids(inspect_files([str(compose)])))


BAD_LOG = """\
INFO speculative config: dflash k=15
torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 2.00 GiB
worker exited with code 137
ValueError: Free memory on device (58.2/119.7 GiB) on startup is less than desired GPU memory utilization (0.9, 107.7 GiB)
|    0   N/A  N/A   41234   C   VLLM::EngineCore      104277MiB |
Initializing a V1 LLM engine with config: {'fuse_gemm_comms': False, 'x': 1}
TypeError: Qwen3Model.forward() got an unexpected keyword argument 'cache_position'
RuntimeError: CUDA error: device-side assert triggered
forward: embed_token failed (dtype F16)
Final estimate: PPL = nan +/- nan
POST /v1/chat/completions 500 Internal Server Error: failed to fetch image_url file:///tmp/x.png No such file
{"detail":[{"loc":["body","chat_template_kwargs","enable_thinking"],"msg":"Input should be a valid boolean"}]}
huggingface_hub.errors.LocalEntryNotFoundError: Cannot find an appropriate cached snapshot folder
IsADirectoryError: [Errno 21] Is a directory: '/models/config.json'
sparse_mla indexer topk step
RuntimeError: CUDA error: an illegal memory access was encountered
"""
CLEAN_LOG = """\
INFO loaded model in 12.3s, gpu memory utilization 0.9
INFO request finished status 200
INFO exit code 0
INFO the docs mention enable_thinking and fuse_gemm_comms
INFO 137 requests served
"""
NEW_LOG_TRAPS = {"51", "72", "85", "98", "101", "112", "115", "116", "117", "119", "123", "131", "140", "142"}


class LogRules(TempDirCase):
    def test_each_new_signature_fires(self):
        self.assertEqual(NEW_LOG_TRAPS - _ids(inspect_logs([str(self.write("bad.log", BAD_LOG))])), set())

    def test_harmless_keyword_mentions_do_not_fire(self):
        self.assertEqual(_ids(inspect_logs([str(self.write("clean.log", CLEAN_LOG))])), set())

    def test_repeated_log_signature_is_bounded_and_reported(self):
        path = self.write("repeat.log", ("worker exited with code 137\n" * 100))
        report = inspect_logs([str(path)])
        self.assertLessEqual(len(report["findings"]), 8)
        self.assertTrue(
            any(item["code"] == "RULE_MATCH_LIMIT" and item.get("trap_id") == "115"
                for item in report["truncations"]),
            report["truncations"],
        )


DEFECTIVE_TEMPLATE = """\
{%- if messages[0].role == 'system' %}{% set sys = messages[0].content %}{% set rest = messages[1:] %}\
{% else %}{% set sys = 'You are a helpful assistant created by Probe Labs. Always answer carefully and politely.' %}\
{% set rest = messages %}{% endif %}
<|im_start|>system
{{ sys }}<|im_end|>
{% for m in rest %}
{%- if m.role == 'assistant' and m.tool_calls %}<|im_start|>assistant
{% for tc in m.tool_calls %}{% if tc.function.arguments is mapping %}{% for k, v in tc.function.arguments|items %}<{{k}}>{{v}}</{{k}}>{% endfor %}{% endif %}{% endfor %}<|im_end|>
{% elif m.role == 'assistant' %}<|im_start|>assistant
<think>

</think>

{{ m.content }}<|im_end|>
{% elif m.role == 'system' %}{{ raise_exception('System message must be at the beginning.') }}
{% else %}<|im_start|>{{ m.role }}
{% if m.content is string %}{{ m.content | replace('/no_think', '') | replace('/think', '') }}\
{% else %}{% for p in m.content %}{% if p.type == 'text' %}{{ p.text }}{% endif %}{% endfor %}{% endif %}<|im_end|>
{% endif %}
{% endfor %}
{%- if add_generation_prompt %}<|im_start|>assistant
{% if enable_thinking is defined and enable_thinking is false %}<think>

</think>

{% else %}<think>
{% endif %}{% endif %}
"""
CLEAN_TEMPLATE = """\
{% for m in messages %}<|im_start|>{{ m.role }}
{% if m.content is string %}{{ m.content }}{% elif m.content %}{% for p in m.content %}\
{% if p.type == 'text' %}{{ p.text }}{% elif p.type == 'image' %}<image>{% endif %}{% if not loop.last %} {% endif %}{% endfor %}{% endif %}
{%- if m.tool_calls %}{% for tc in m.tool_calls %}<tool_call>{{ tc.function.name }} \
{{ tc.function.arguments if tc.function.arguments is string else tc.function.arguments|tojson }}</tool_call>{% endfor %}{% endif %}<|im_end|>
{% endfor %}{% if add_generation_prompt %}<|im_start|>assistant
{% endif %}"""
RELOCATING_TEMPLATE = (
    "{% for m in messages %}{% if m.role == 'user' %}[INST] "
    "{% if loop.last and messages[0].role == 'system' %}{{ messages[0].content }}\n\n{% endif %}"
    "{{ m.content }}[/INST]{% elif m.role == 'assistant' %} {{ m.content }}</s>{% endif %}{% endfor %}"
)
LIST_REPR_TEMPLATE = "{% for m in messages %}<|im_start|>{{ m.role }}\n{{ m.content }}<|im_end|>\n{% endfor %}"
ALTERNATION_TEMPLATE = (
    "{% set ns = namespace(i=0) %}{% for m in messages %}{% if m.role in ['user', 'assistant'] %}"
    "{% if (m.role == 'user') != (ns.i % 2 == 0) %}"
    "{{ raise_exception('Conversation roles must alternate user/assistant/user/assistant/...') }}{% endif %}"
    "{% if not m.tool_calls %}{% set ns.i = ns.i + 1 %}{% endif %}{% endif %}{{ m.role }}: {{ m.content }}\n"
    "{% endfor %}"
)


class TemplateAnalyzer(TempDirCase):
    def template(self, text: str) -> dict:
        return inspect_template(self.write("chat_template.jinja", text))

    def test_defective_template_shows_each_defect(self):
        found = _ids(self.template(DEFECTIVE_TEMPLATE))
        for trap in ("04", "24", "25", "30", "38", "43", "57", "66", "68", "83", "113"):
            self.assertIn(trap, found, trap)

    def test_clean_template_has_no_findings(self):
        report = self.template(CLEAN_TEMPLATE)
        self.assertEqual(report["findings"], [], report)

    def test_system_relocation(self):
        self.assertTrue({"82", "93"} <= _ids(self.template(RELOCATING_TEMPLATE)))

    def test_list_content_rendered_as_python(self):
        self.assertIn("67", _ids(self.template(LIST_REPR_TEMPLATE)))

    def test_tool_round_trip_then_user_is_unrenderable(self):
        self.assertIn("84", _ids(self.template(ALTERNATION_TEMPLATE)))

    def test_real_qwen38_template(self):
        found = _ids(inspect_template(QWEN_TEMPLATE))
        # Measured on the shipped fixture: injected reasoning-effort preamble,
        # empty think shells in history, glued text parts, string tool args
        # that fail to render, and string "false" turning thinking on.
        self.assertTrue({"25", "38", "43", "57", "68", "83"} <= found, found)

    def test_missing_jinja2_is_said_plainly_not_reported_clean(self):
        from unittest import mock

        with mock.patch("minefield.template_inspector._jinja_available", return_value=False):
            report = self.template(DEFECTIVE_TEMPLATE)
        self.assertTrue(any("jinja2 is not installed" in n for n in report["notes"]), report)
        self.assertEqual(_ids(report), {"24"})

    def test_missing_template_is_reported(self):
        self.write("config.json", "{}")
        self.write("tokenizer_config.json", json.dumps({"bos_token": "<s>"}))
        self.assertEqual(_ids(inspect_template(self.dir)), {"56"})

    def test_sandbox_blocks_python_internals(self):
        report = self.template("{{ messages.__class__.__mro__ }}")
        self.assertEqual(report["findings"], [])
        self.assertTrue(any("does not render" in n for n in report["notes"]))


# 10^10 loop iterations: the sandbox caps each range(), not the nesting.
HANGING_TEMPLATE = (
    "{% for i in range(100000) %}{% for j in range(100000) %}{% endfor %}{% endfor %}"
    "{% for m in messages %}{{ m.content }}{% endfor %}"
)
# Renders a plain conversation at once and hangs only when tools are passed,
# so the early probes run and the tool probes hit the timeout.
HANGS_ON_TOOLS_TEMPLATE = (
    "{% if tools %}{% for i in range(100000) %}{% for j in range(100000) %}{% endfor %}{% endfor %}{% endif %}"
    "{% for m in messages %}<|im_start|>{{ m.role }}\n{{ m.content }}<|im_end|>\n{% endfor %}"
)


class TemplateRenderTimeout(TempDirCase):
    GUARD_S = 20  # without the timeout these renders run for hours; fail instead of hanging the suite

    def bounded(self, fn):
        import threading
        from unittest import mock

        out: dict = {}
        with mock.patch("minefield.template_inspector.RENDER_TIMEOUT_S", 0.5):
            worker = threading.Thread(target=lambda: out.setdefault("report", fn()), daemon=True)
            worker.start()
            worker.join(self.GUARD_S)
        self.assertFalse(worker.is_alive(), "template render did not time out")
        return out["report"]

    def test_hanging_template_is_cut_off_and_said_not_clean(self):
        path = self.write("chat_template.jinja", HANGING_TEMPLATE)
        report = self.bounded(lambda: inspect_template(path))
        self.assertEqual(report["findings"], [])
        self.assertTrue(any("longer than 0.5s" in n and "not a clean result" in n
                            for n in report["notes"]), report["notes"])

    def test_one_timeout_skips_the_remaining_probes(self):
        import time

        path = self.write("chat_template.jinja", HANGS_ON_TOOLS_TEMPLATE)
        start = time.monotonic()
        report = self.bounded(lambda: inspect_template(path))
        # Every probe after the first tool render would otherwise wait out its own timeout.
        self.assertLess(time.monotonic() - start, 3.0)
        self.assertIn("not a clean result", report["notes"][0])
        skipped = {n.split(":")[0] for n in report["notes"] if "not checked (RenderTimeout" in n}
        # The probes before the first tool render ran; everything from it on was skipped.
        self.assertTrue({"tool arguments", "list content", "history reasoning"} <= skipped, skipped)
        self.assertFalse({"default system prompt", "generation prompt"} & skipped, skipped)

    def test_scan_finishes_on_a_hanging_template(self):
        self.write("model/config.json", "{}")
        self.write("model/chat_template.jinja", HANGING_TEMPLATE)
        report = self.bounded(lambda: scan([str(self.dir / "model")]))
        self.assertTrue(any("not a clean result" in n for n in report["notes"]), report["notes"])

    def test_existing_trace_function_is_restored(self):
        def tracer(frame, event, arg):
            return None

        path = self.write("chat_template.jinja", CLEAN_TEMPLATE)
        previous = sys.gettrace()
        sys.settrace(tracer)
        try:
            inspect_template(path)
            self.assertIs(sys.gettrace(), tracer)
        finally:
            sys.settrace(previous)


class ModelFolder(TempDirCase):
    def test_risky_config_and_files(self):
        folder = self.dir / "Qwen3-8B-NVFP4"
        folder.mkdir()
        (folder / "config.json").write_text(json.dumps({
            "model_type": "qwen3", "sliding_window": 4096, "use_sliding_window": False,
            "num_hidden_layers": 36, "max_position_embeddings": 131072,
            "rope_scaling": {"rope_type": "yarn", "factor": 4.0, "original_max_position_embeddings": 32768},
            "num_nextn_predict_layers": 1,
            "quantization_config": {"quant_method": "compressed-tensors", "ignore": ["lm_head", "mtp.layers.0.mlp"]},
        }))
        (folder / "model.safetensors").write_text("x")
        os.link(folder / "model.safetensors", self.dir / "stock.safetensors")
        self.assertEqual(_ids(inspect_model_folder(folder)),
                         {"10", "21", "55", "61", "71", "89", "109", "143"})

    def test_clean_folder(self):
        self.write("config.json", json.dumps({"model_type": "llama", "max_position_embeddings": 8192}))
        self.write("generation_config.json", "{}")
        self.assertEqual(_ids(inspect_model_folder(self.dir)), set())

    def test_hf_cache_ref_with_trailing_newline(self):
        root = self.dir / "models--org--m"
        self.write("models--org--m/refs/main", "abcdef0123456789abcdef0123456789abcdef01\n")
        snap = root / "snapshots" / "abc"
        snap.mkdir(parents=True)
        (snap / "config.json").write_text(json.dumps({"model_type": "llama"}))
        (snap / "generation_config.json").write_text("{}")
        self.assertEqual(_ids(inspect_model_folder(snap)), {"131"})

    def test_cache_ref_directory_visit_budget_counts_empty_directories(self):
        from unittest import mock

        root = self.dir / "models--org--m"
        for i in range(6):
            (root / "refs" / f"empty-{i}").mkdir(parents=True)
        snap = root / "snapshots" / "abc"
        snap.mkdir(parents=True)
        (snap / "config.json").write_text(json.dumps({"model_type": "llama"}))
        with mock.patch("minefield.model_inspector.MAX_CACHE_REF_VISITS", 3):
            report = inspect_model_folder(snap)
        self.assertTrue(
            any("cache-ref inspection stopped after 3 directory entries" in note
                for note in report["notes"]),
            report["notes"],
        )

    def test_model_folder_entry_listing_is_bounded(self):
        from unittest import mock

        folder = self.dir / "model"
        folder.mkdir()
        (folder / "config.json").write_text(json.dumps({"model_type": "llama"}))
        for i in range(5):
            (folder / f"extra-{i}.bin").write_text("x")
        with mock.patch("minefield.model_inspector.MAX_MODEL_DIR_ENTRIES", 2):
            report = inspect_model_folder(folder)
        self.assertTrue(
            any("model-folder entry inspection stopped after 2 entries" in note
                for note in report["notes"]),
            report["notes"],
        )


class EvalResults(TempDirCase):
    def test_measurement_traps_in_results(self):
        rows = [{"arm": "thinking", "finish_reason": "length" if i % 3 == 0 else "stop",
                 "content": "" if i % 3 == 0 else "B", "correct": i % 3 != 0} for i in range(40)]
        rows += [{"arm": "baseline", "finish_reason": "stop", "content": "A", "correct": True} for _ in range(40)]
        rows.append({"arm": "baseline", "finish_reason": "stop", "content": None,
                     "reasoning_content": "The answer is 4", "correct": False})
        rows.append({"arm": "baseline", "finish_reason": "tool_calls", "content": "",
                     "tool_calls": [{"id": "x"}], "correct": False})
        path = self.write("results.json", json.dumps({"results": rows}))
        self.assertEqual(_ids(inspect_results(path)), {"12", "16", "36", "42", "64"})

    def test_all_zero_openai_envelopes(self):
        lines = [json.dumps({"model": "m", "response": {"choices": [
            {"finish_reason": "stop", "message": {"content": "x"}}]}, "score": 0}) for _ in range(20)]
        self.assertEqual(_ids(inspect_results(self.write("run.jsonl", "\n".join(lines)))), {"37"})

    def test_healthy_results(self):
        rows = [{"arm": a, "finish_reason": "stop", "content": "ok", "correct": i % 2 == 0}
                for a in ("a", "b") for i in range(30)]
        self.assertEqual(_ids(inspect_results(self.write("good.json", json.dumps(rows)))), set())

    def test_unrecognised_json_is_not_reported_clean(self):
        report = inspect_results(self.write("package.json", json.dumps({"name": "x", "version": "1"})))
        self.assertTrue(report["notes"])


class ScanCommand(TempDirCase):
    def test_scan_routes_each_file_to_its_detector(self):
        self.write("launch.sh", RISKY_LAUNCH)
        self.write("logs/server.log", BAD_LOG)
        self.write("model/config.json", json.dumps({"model_type": "llama"}))
        self.write("model/chat_template.jinja", DEFECTIVE_TEMPLATE)
        report = scan([str(self.dir)])
        kinds = {s["kind"] for s in report["scanned"]}
        self.assertTrue({"config", "log", "model folder"} <= kinds, kinds)
        self.assertTrue({"13", "115", "83", "21"} <= set(report["traps"]))

    def test_nothing_matches_says_so_without_calling_it_safe(self):
        self.write("notes.txt", "shopping list: eggs, bread\n")
        report = scan([str(self.dir)])
        self.assertEqual(report["findings"], [])
        self.assertIn("not that the setup is safe", report["warning"])

    def test_symlinks_are_refused(self):
        target = self.write("real.sh", RISKY_LAUNCH)
        link = self.dir / "link.sh"
        link.symlink_to(target)
        report = scan([str(link)])
        self.assertEqual(report["findings"], [])
        self.assertTrue(any("symlink" in n for n in report["notes"]))

    def test_entry_visit_budget_counts_empty_directories(self):
        from unittest import mock

        for i in range(12):
            (self.dir / f"empty-{i}").mkdir()
        with mock.patch("minefield.scan.MAX_ENTRY_VISITS", 5):
            report = scan([str(self.dir)])
        self.assertIn(
            {"code": "ENTRY_VISIT_LIMIT", "limit": 5},
            report["truncations"],
        )
        self.assertTrue(any("5-entry visit limit" in note for note in report["notes"]))

    def test_scan_propagates_detector_truncation_metadata(self):
        path = self.write("repeat.sh", ("reasoning_effort=x\n" * 100))
        report = scan([str(path)])
        self.assertTrue(
            any(item["code"] == "RULE_MATCH_LIMIT" and item.get("detector") == "config"
                for item in report["truncations"]),
            report["truncations"],
        )

    def test_scan_finding_output_has_a_global_cap(self):
        from unittest import mock

        path = self.write("launch.sh", RISKY_LAUNCH)
        with mock.patch("minefield.scan.MAX_SCAN_FINDINGS", 1):
            report = scan([str(path)])
        self.assertEqual(len(report["findings"]), 1)
        self.assertTrue(
            any(item["code"] == "SCAN_FINDING_LIMIT" and item["limit"] == 1
                for item in report["truncations"]),
            report["truncations"],
        )

    def test_cli_json_when_piped_and_text_on_request(self):
        self.write("launch.sh", RISKY_LAUNCH)
        env = {**os.environ, "PYTHONPATH": str(ROOT)}
        piped = subprocess.run([sys.executable, "-m", "minefield", "scan", str(self.dir)],
                               capture_output=True, text=True, env=env, cwd=ROOT, check=True)
        self.assertIn("13", json.loads(piped.stdout)["traps"])
        text = subprocess.run([sys.executable, "-m", "minefield", "scan", "--text", str(self.dir)],
                              capture_output=True, text=True, env=env, cwd=ROOT, check=True)
        self.assertIn("Trap 13", text.stdout)
        self.assertIn("read:", text.stdout)


class CoverageFloor(unittest.TestCase):
    def test_automated_coverage_does_not_regress(self):
        summary = build_coverage(load_registry())["summary"]
        self.assertGreaterEqual(summary["any_automated_check"], 87)



class McpScanTool(TempDirCase):
    def test_scan_is_confined_to_allowed_roots(self):
        from minefield.mcp_server import call_tool

        inside = self.write("inside/launch.sh", RISKY_LAUNCH)
        outside = self.write("outside/launch.sh", RISKY_LAUNCH)
        registry = load_registry()
        result = call_tool("scan_files", {"paths": [str(inside)]}, registry,
                           allowed_roots=[str(self.dir / "inside")])
        self.assertIn("13", result["traps"])
        with self.assertRaises(ValueError):
            call_tool("scan_files", {"paths": [str(outside)]}, registry,
                      allowed_roots=[str(self.dir / "inside")])
        with self.assertRaises(ValueError):
            call_tool("scan_files", {"paths": [str(inside)]}, registry, allowed_roots=[])


if __name__ == "__main__":
    unittest.main()
