"""Offline contracts: catalogue declarations must match executable probes."""
from __future__ import annotations

import ast
import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_server import FixtureLane, llamacpp_props
from minefield.api import RunResult, _load_doctor, plan_checks, result_to_doctor_json, run_checks, summarize

md = _load_doctor()


def emitted_traps(function_name):
    tree = ast.parse((ROOT / 'doctor/minefield_doctor.py').read_text())
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    seen, found = set(), set()

    def walk(name):
        if name in seen or name not in functions:
            return
        seen.add(name)
        for node in ast.walk(functions[name]):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                walk(node.func.id)
            if (isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == 'doc'
                    and node.func.attr in {'ok', 'problem', 'inconclusive', 'skip'}):
                # Dynamic trap declarations must add an explicit reviewed contract;
                # do not silently omit an expression the validator cannot read.
                found.update(ast.literal_eval(node.args[0]))
    walk(function_name)
    return found & set(md.TRAP_PATHS)


class CatalogueContract(unittest.TestCase):
    def test_declared_ids_equal_every_reachable_canonical_finding(self):
        for spec in md.PROBE_SPECS:
            with self.subTest(probe=spec.id):
                self.assertEqual(set(spec.traps), emitted_traps(spec.invoke.__name__))

    def test_zero_budget_history_plan_includes_orphaned_close(self):
        plan = plan_checks(max_requests=0, preferred_trap_ids=['02'])
        self.assertIn('history_assembly', plan.selected_ids)
        history = next(p for p in plan.selected if p.id == 'history_assembly')
        self.assertIn('02', history.traps)

    def test_corrected_specialised_traps_are_in_the_plan(self):
        plan = plan_checks(mode='doctor', probe_ids=['tool_choice_gate', 'kwarg_deadness'])
        self.assertEqual({t for p in plan.selected for t in p.traps}, {'07', '78'})
        self.assertEqual(len(plan.selected), 2)

    def test_explicit_selection_never_overrides_lite_eligibility(self):
        plan = plan_checks(probe_ids=['minicpm_short_answer_channel'])
        self.assertEqual(plan.selected, ())
        self.assertIn('not_lite_eligible', next(p.reason for p in plan.skipped
                                             if p.id == 'minicpm_short_answer_channel'))

    def test_bad_options_fail_before_detection(self):
        for kwargs in ({'max_requests': -1}, {'max_requests': True}, {'max_requests': 1.5},
                       {'probe_ids': ['not_a_probe']}, {'probe_ids': 'generation_readiness'}):
            with self.subTest(kwargs=kwargs), patch('minefield.api.detect_target') as detect:
                with self.assertRaises(ValueError):
                    plan_checks(base_url='http://example.invalid', detect=True, **kwargs)
                detect.assert_not_called()

    def test_every_probe_has_enough_budget_on_fixture_scenarios(self):
        scenarios = [{}, {'explicit_off_honored': False}, {'reject_everything': True},
                     {'props': llamacpp_props()}, {'tool_choice_supported': False}]
        for flags in scenarios:
            with FixtureLane(**flags) as base:
                for spec in md.PROBE_SPECS:
                    with self.subTest(flags=flags, probe=spec.id):
                        plan = plan_checks(base_url=base, mode='doctor',
                                           probe_ids=[spec.id], max_requests=spec.request_cost)
                        result = run_checks(plan)
                        self.assertIsNone(result.error)
                        self.assertFalse(result.budget_exceeded)
                        self.assertLessEqual(result.requests_executed, spec.request_cost)
                        reported = {t for f in result.findings for t in f['traps']
                                    if t in md.TRAP_PATHS}
                        self.assertTrue(reported <= set(spec.traps))

    def test_planned_order_is_invoked_order(self):
        with FixtureLane() as base:
            plan = plan_checks(base_url=base, mode='doctor', max_requests=4,
                               probe_ids=['request_validation', 'generation_readiness'])
            plan = replace(plan, selected=tuple(reversed(plan.selected)))
            result = run_checks(plan)
        self.assertEqual([r['id'] for r in result.probe_runs], list(plan.selected_ids))
        self.assertEqual(sum(r['requests_made'] for r in result.probe_runs), result.requests_executed)
        payload = result_to_doctor_json(result)
        self.assertEqual(payload['not_run_probes'], [])
        self.assertEqual(payload['invoked_probes'], list(plan.selected_ids))

    def test_budget_exhaustion_records_partial_and_unstarted_work(self):
        with FixtureLane() as base:
            plan = plan_checks(base_url=base, mode='doctor',
                               probe_ids=['request_validation', 'generation_readiness'])
            # Simulate an out-of-date caller handing run_checks a tighter budget.
            result = run_checks(replace(plan, max_requests=0))
        self.assertTrue(result.budget_exceeded)
        self.assertEqual(result.requests_executed, 0)
        payload = result_to_doctor_json(result)
        self.assertEqual(payload['probe_runs'][0]['status'], 'BUDGET_EXHAUSTED')
        self.assertEqual(payload['not_run_probes'], ['generation_readiness'])
        self.assertIn('PROBE_BUDGET_EXHAUSTED', [f['code'] for f in payload['findings']])

    def test_lower_level_summaries_cannot_clear_conflicting_traps(self):
        for level in ("PROBLEM", "INCONCLUSIVE", "UNKNOWN"):
            with self.subTest(level=level):
                doc = md.Doc()
                doc.ok(["23"], "one assertion passed", asserts=[md.A("passed", True)])
                doc._add(level, ["23"], "another assertion did not", "TEST", None,
                         [md.A("complete", False, held=False)])
                self.assertNotIn("23", md.coverage(doc)["clean"])
                self.assertIn("23", md.coverage(doc)["conflicting_verdicts"])
                plan = plan_checks(max_requests=0)
                result = RunResult(plan, "fixture", "fixture", 0, 0, 0, findings=doc.findings)
                self.assertNotIn("23", summarize(result).trap_ids_clean)
                self.assertEqual(len(result.findings), 2)  # preserve both observations

    def test_probe_exception_preserves_evidence_without_echoing_private_text(self):
        with FixtureLane() as base:
            plan = plan_checks(base_url=base, mode='doctor', probe_ids=['generation_readiness'])
            with patch.object(md, 'check_generation_readiness', side_effect=ValueError('PRIVATE BODY')):
                result = run_checks(plan)
        payload = result_to_doctor_json(result)
        self.assertEqual(payload['probe_runs'][0]['status'], 'ERROR')
        self.assertEqual(payload['error'], 'probe_execution_error:ValueError')
        self.assertNotIn('PRIVATE BODY', json.dumps(payload))


class ValidationFailureContract(unittest.TestCase):
    def test_transient_or_auth_errors_cannot_be_validation_clean(self):
        baseline = (200, {'message': {'content': 'OK', 'tool_calls': []}}, {})
        checks = [(md.check_request_validation, '77'), (md.check_model_identity, '141'),
                  (md.check_tool_choice_gate, '78')]
        for check, trap in checks:
            for status in (None, 401, 403, 408, 429, 500, 502, 503):
                with self.subTest(check=check.__name__, status=status):
                    doc = md.Doc(); doc.model = 'fixture'; doc.stack = 'sglang'
                    with patch.object(md, 'chat', side_effect=[baseline, (status, None, '')]):
                        check(doc, 'http://example.invalid/v1', None)
                    self.assertNotIn(trap, doc.trap_ids('OK'))
                    self.assertIn(trap, doc.trap_ids('UNKNOWN'))

    def test_tool_choice_malformed_200_is_not_a_rejection(self):
        doc = md.Doc(); doc.model = 'fixture'
        with patch.object(md, 'chat', side_effect=[
            (200, {'message': {'tool_calls': []}}, {}), (200, None, 'bad JSON')]):
            md.check_tool_choice_gate(doc, 'http://example.invalid/v1', None)
        self.assertNotIn('78', doc.trap_ids('OK'))


if __name__ == '__main__':
    unittest.main()
