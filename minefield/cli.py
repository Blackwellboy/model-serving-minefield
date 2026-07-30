"""Command line interface for safe, multi-modal Minefield diagnosis."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .coverage import build_coverage
from .doctor_adapter import run as run_doctor
from .generator import build, verify
from .inline_system import classify_manifest, inspect_template, load_manifest
from .log_inspector import inspect_logs
from .matching import diagnose
from .registry import load_registry
from .static_inspector import inspect_files
from .support_bundle import plan, write_bundle

CONDITION_FLAGS = (
    "gpu-architecture", "device-class", "node-count", "parallelism",
    "topology", "stack-version", "model-family", "exact-checkpoint",
    "quantization", "context-regime", "concurrency-regime",
    "failure-stage", "operating-system",
)


def _emit(value: Any, as_json: bool = True) -> None:
    if as_json:
        print(json.dumps(value, indent=2, sort_keys=True))
    else:
        print(value)


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="minefield")
    sub = ap.add_subparsers(dest="command", required=True)
    quick = sub.add_parser("quick", help="run the existing read-only endpoint doctor")
    quick.add_argument("doctor_args", nargs=argparse.REMAINDER)
    for name in ("inspect-config", "inspect-logs"):
        cmd = sub.add_parser(name)
        cmd.add_argument("paths", nargs="+")
        cmd.add_argument(
            "--allowed-root", action="append", required=True,
            help="approved filesystem root; repeat for additional roots",
        )
    guide = sub.add_parser("guide")
    guide.add_argument("symptom")
    guide.add_argument("--stack")
    guide.add_argument("--model")
    guide.add_argument("--version")
    for flag in CONDITION_FLAGS:
        guide.add_argument(f"--{flag}")
    guide.add_argument("--direct-probe-trap", action="append", default=[])
    guide.add_argument(
        "--direct-probe-result", action="append", default=[], metavar="TRAP=RESULT",
        help="record confirmed, refuted, or inconclusive for an explicit trap probe",
    )
    guide.add_argument("--mechanism-probe-trap", action="append", default=[])
    sub.add_parser("diagnose")
    coverage = sub.add_parser("coverage")
    coverage.add_argument("--json", action="store_true")
    agent = sub.add_parser("agent-bundle")
    agent.add_argument("--verify", action="store_true")
    bundle = sub.add_parser("bundle")
    bundle.add_argument("--config", action="append", default=[])
    bundle.add_argument("--log", action="append", default=[])
    bundle.add_argument("--doctor-report")
    bundle.add_argument("--output", default="minefield-support-bundle.zip")
    bundle.add_argument("--no-write", action="store_true")
    inline = sub.add_parser(
        "classify-inline-system",
        help="classify bounded, already-rendered inline-system evidence",
    )
    inline.add_argument("--manifest", required=True)
    inline.add_argument(
        "--template-path",
        help="optional local Jinja/source file to hash; it is never executed",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "quick":
        return run_doctor(argv[1:])
    args = parser().parse_args(argv)
    registry = load_registry()
    if args.command == "inspect-config":
        _emit(inspect_files(args.paths, args.allowed_root))
    elif args.command == "inspect-logs":
        _emit(inspect_logs(args.paths, args.allowed_root))
    elif args.command == "guide":
        direct_probe_results = {}
        for item in args.direct_probe_result:
            trap_id, separator, outcome = item.partition("=")
            if not separator or outcome not in {"confirmed", "refuted", "inconclusive"}:
                raise SystemExit(
                    "--direct-probe-result must be TRAP=confirmed|refuted|inconclusive"
                )
            direct_probe_results[trap_id] = outcome
        conditions = {
            flag.replace("-", "_"): getattr(args, flag.replace("-", "_"))
            for flag in CONDITION_FLAGS
            if getattr(args, flag.replace("-", "_")) is not None
        }
        _emit(diagnose(
            registry, args.symptom, stack=args.stack, model=args.model,
            version=args.version, conditions=conditions,
            direct_probe_trap_ids=args.direct_probe_trap,
            direct_probe_results=direct_probe_results,
            mechanism_probe_trap_ids=args.mechanism_probe_trap,
        ))
    elif args.command == "diagnose":
        if not sys.stdin.isatty():
            raise SystemExit("diagnose requires an interactive terminal")
        symptom = input("What are you seeing? ").strip()
        stack = input("Serving stack and version? ").strip()
        model = input("Model and revision? ").strip()
        _emit(diagnose(registry, symptom, stack=stack, model=model))
    elif args.command == "coverage":
        value = build_coverage(registry)["summary"]
        _emit(value if args.json else "\n".join(f"{k}: {v}" for k, v in value.items()),
              as_json=args.json)
    elif args.command == "agent-bundle":
        _emit(verify() if args.verify else build())
    elif args.command == "bundle":
        bundle_plan = plan(configs=args.config, logs=args.log, doctor_report=args.doctor_report)
        if args.no_write:
            _emit(bundle_plan["preview"])
        else:
            _emit(write_bundle(args.output, bundle_plan))
    elif args.command == "classify-inline-system":
        value = classify_manifest(load_manifest(args.manifest))
        if args.template_path:
            value["template_source"] = inspect_template(args.template_path)
        _emit(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
