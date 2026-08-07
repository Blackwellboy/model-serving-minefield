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
from .inline_system import EvidenceError, classify_manifest, inspect_template, load_manifest
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
    # Offline research-integrity tools (no endpoint mutation).
    ep = sub.add_parser(
        "evidence-preflight",
        help="validate an Evidence Packet v1 (offline; no endpoint calls)",
    )
    ep.add_argument(
        "--packet",
        required=True,
        help="path to Evidence Packet JSON (schema docs/evidence-packet.schema.json)",
    )
    ep.add_argument(
        "--artifact-root",
        help="directory used to resolve relative artifact paths for SHA256 checks",
    )
    br = sub.add_parser(
        "blind-review",
        help="derive a blind-review packet (strips proposer verdict/confidence)",
    )
    br.add_argument("--packet", required=True, help="path to full Evidence Packet JSON")
    br.add_argument("--out", help="write blind wrapper JSON to this path")
    ut = sub.add_parser(
        "upstream-triage",
        help="offline map of changed paths to risk surfaces (never NEW_TRAP_FOUND)",
    )
    ut.add_argument(
        "--changes",
        help="file of paths (git diff --name-only); stdin if omitted",
    )
    pr = sub.add_parser(
        "promotion-receipt",
        help="validate a Promotion Receipt (records provenance; does not allocate traps)",
    )
    pr.add_argument("--receipt", required=True, help="path to promotion receipt JSON")
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
        try:
            value = classify_manifest(load_manifest(args.manifest))
            if args.template_path:
                value["template_source"] = inspect_template(args.template_path)
            _emit(value)
        except (EvidenceError, OSError) as exc:
            print(json.dumps({
                "classification": "INCONCLUSIVE",
                "error": type(exc).__name__,
                "reason": str(exc),
            }, sort_keys=True), file=sys.stderr)
            return 2
    elif args.command == "evidence-preflight":
        from .evidence_packet import preflight_path

        root = Path(args.artifact_root) if args.artifact_root else None
        report = preflight_path(args.packet, artifact_root=root)
        _emit(report)
        status = report.get("status")
        if status == "PASS":
            return 0
        if status == "FAIL":
            return 2
        return 3
    elif args.command == "blind-review":
        from .blind_review import assert_no_leak, derive_blind_packet
        from .evidence_packet import load_packet

        path = Path(args.packet)
        if not path.is_file():
            _emit({
                "status": "FAIL",
                "error": "packet_not_found",
                "message": f"not a readable file: {path}",
            })
            return 2
        try:
            full = load_packet(path)
        except (OSError, json.JSONDecodeError) as exc:
            _emit({
                "status": "FAIL",
                "error": "packet_json_invalid",
                "message": str(exc),
            })
            return 2
        wrapper = derive_blind_packet(full)
        leaks = assert_no_leak(wrapper)
        if leaks:
            wrapper["leak_check"] = {"status": "FAIL", "leaks": leaks}
        else:
            wrapper["leak_check"] = {"status": "PASS", "leaks": []}
        _emit(wrapper)
        if args.out:
            Path(args.out).write_text(
                json.dumps(wrapper, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return 0 if not leaks else 2
    elif args.command == "upstream-triage":
        from .upstream_change_triage import triage_file, triage_from_text

        if args.changes:
            cpath = Path(args.changes)
            if not cpath.is_file():
                _emit({
                    "status": "UNKNOWN",
                    "error": "changes_not_found",
                    "message": f"not a readable file: {cpath}",
                    "observed_count": 0,
                    "new_trap_found": False,
                })
                return 3
            report = triage_file(cpath)
        else:
            report = triage_from_text(sys.stdin.read())
        _emit(report)
        return 0 if report.get("observed_count", 0) > 0 else 3
    elif args.command == "promotion-receipt":
        from .promotion_receipt import validate_receipt

        path = Path(args.receipt)
        if not path.is_file():
            _emit({
                "status": "FAIL",
                "error": "receipt_not_found",
                "message": f"not a readable file: {path}",
            })
            return 2
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _emit({
                "status": "FAIL",
                "error": "receipt_json_invalid",
                "message": str(exc),
            })
            return 2
        report = validate_receipt(doc)
        _emit(report)
        status = report.get("status")
        if status == "PASS":
            return 0
        if status == "FAIL":
            return 2
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
