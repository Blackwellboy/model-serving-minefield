"""CLI/API/MCP option propagation; all endpoint operations are mocked."""
from __future__ import annotations

import contextlib
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from minefield.api import TargetInfo, plan_checks, run_checks
from minefield.cli import main
from minefield.mcp_server import call_tool
from minefield.probe_options import validate_operator_inputs
from minefield.registry import load_registry
from minefield.unified import diagnose_environment

REGISTRY = load_registry()
OPTIONS = dict(hf_revision='fixture-pinned-revision', server_max_tokens=32,
               benchmark_target_tokens=100, benchmark_prompt_text='approved synthetic text',
               thinking_budget_marker_ids='100,101')


class OperatorInputTests(unittest.TestCase):
    def test_valid_options_round_trip(self):
        self.assertEqual(validate_operator_inputs(**OPTIONS), OPTIONS)

    def test_invalid_inputs_fail_before_any_network(self):
        bad = [dict(hf_revision=''), dict(server_max_tokens=True), dict(server_max_tokens=256),
               dict(server_max_tokens=0), dict(benchmark_target_tokens=32),
               dict(benchmark_target_tokens=32, benchmark_prompt_text='x' * 8193),
               dict(thinking_budget_marker_ids='1'), dict(thinking_budget_marker_ids='1,-1')]
        for kwargs in bad:
            with self.subTest(kwargs=list(kwargs)), patch('minefield.unified.detect_target') as detect:
                with self.assertRaises(ValueError):
                    diagnose_environment(REGISTRY, base_url='http://example.invalid', **kwargs)
                detect.assert_not_called()

    def test_run_api_passes_exact_options_to_doctor(self):
        plan = plan_checks(probe_ids=['prompt_target_tokens'], mode='doctor', max_requests=0)
        from minefield.api import _load_doctor
        md = _load_doctor()
        with patch.object(md, 'detect_stack', return_value=True), patch.object(md, 'run') as run:
            result = run_checks(plan, **OPTIONS)
        args = run.call_args.args[3]
        for key, value in OPTIONS.items():
            self.assertEqual(getattr(args, key), value)
        self.assertEqual(result.requests_executed, 0)

    def test_unified_passes_revision_and_parameters_to_runner(self):
        target = TargetInfo('http://example.invalid/v1', 'http://example.invalid', model='fixture')
        with (patch('minefield.unified.detect_target', return_value=target),
              patch('minefield.unified.run_checks') as run,
              patch('minefield.unified.result_to_doctor_json', return_value={'findings': []})):
            diagnose_environment(REGISTRY, base_url=target.base_url, mode='doctor',
                                 probe_ids=['prompt_target_tokens'], **OPTIONS)
        for key, value in OPTIONS.items():
            self.assertEqual(run.call_args.kwargs[key], value)
        self.assertEqual(run.call_args.args[0].selected_ids, ('prompt_target_tokens',))

    def test_cli_passes_options_to_unified(self):
        argv = ['diagnose', 'test', '--base-url', 'http://example.invalid', '--mode', 'doctor',
                '--probe', 'prompt_target_tokens', '--hf-revision', OPTIONS['hf_revision'],
                '--server-max-tokens', '32', '--benchmark-target-tokens', '100',
                '--benchmark-prompt-text', OPTIONS['benchmark_prompt_text'],
                '--thinking-budget-marker-ids', '100,101', '--json']
        with patch('minefield.cli.diagnose_environment', return_value={}) as diagnose:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(argv), 0)
        for key, value in OPTIONS.items():
            self.assertEqual(diagnose.call_args.kwargs[key], value)
        self.assertEqual(diagnose.call_args.kwargs['probe_ids'], ['prompt_target_tokens'])

    def test_mcp_passes_options_without_adding_a_network_route(self):
        args = dict(symptom='test', probe_ids=['prompt_target_tokens'], **OPTIONS)
        with patch('minefield.mcp_server.diagnose_environment', return_value={}) as diagnose:
            call_tool('diagnose_environment', args, REGISTRY)
        for key, value in OPTIONS.items():
            self.assertEqual(diagnose.call_args.kwargs[key], value)

    def test_cli_unknown_selection_fails_with_no_traceback_or_detection(self):
        for args in (['doctor-plan', '--probe', 'not-real'],
                     ['diagnose', '--base-url', 'http://example.invalid', '--probe', 'not-real']):
            with (patch('minefield.api.detect_target') as detect,
                  patch('minefield.unified.detect_target') as detect2,
                  contextlib.redirect_stderr(io.StringIO()) as err):
                self.assertEqual(main(args), 2)
                self.assertNotIn('Traceback', err.getvalue())
                detect.assert_not_called(); detect2.assert_not_called()

    def test_plan_cli_selects_only_requested_probe(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(['doctor-plan', '--mode', 'doctor', '--probe',
                                   'minicpm_short_answer_channel', '--max-requests', '2']), 0)
        payload = json.loads(out.getvalue())
        self.assertEqual([p['id'] for p in payload['selected_probes']], ['minicpm_short_answer_channel'])
        self.assertEqual(payload['network_calls_made'], 0)


if __name__ == '__main__':
    unittest.main()
