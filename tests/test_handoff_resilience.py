from __future__ import annotations

import unittest
from unittest.mock import patch

from investor_council_shell.app import InvestorCouncilBackend
from investor_council_shell.codex_bridge import codex_restart_required, perform_handoff


class HandoffResilienceTests(unittest.TestCase):
    def test_perform_handoff_uses_injection_path_without_crashing(self) -> None:
        with patch('investor_council_shell.codex_bridge.skill_installed', return_value=True),              patch('investor_council_shell.codex_bridge._codex_installed', return_value=True),              patch('investor_council_shell.codex_bridge.codex_logged_in', return_value=True),              patch('investor_council_shell.codex_bridge._copy_to_clipboard', return_value=True),              patch('investor_council_shell.codex_bridge._launch_codex', return_value=(True, 'ok')),              patch('investor_council_shell.codex_bridge.auto_injection_available', return_value=True),              patch('investor_council_shell.codex_bridge._inject_prompt', return_value=(True, 'sent', 'existing_thread')):
            result = perform_handoff(
                mentor_name='Livermore',
                market_notes='index range',
                position='30%',
                symbol='ABC',
                question='What next?',
            )

        self.assertTrue(result['ok'])
        self.assertEqual(result['mode'], 'auto_sent')
        self.assertEqual(result['thread_action'], 'existing_thread')

    def test_codex_restart_required_after_skill_sync(self) -> None:
        with patch('investor_council_shell.codex_bridge.load_status', return_value={'skill_synced_at': '2026-04-09T20:25:18'}),              patch('investor_council_shell.codex_bridge._codex_process_info', return_value={'StartTime': '2026-04-08T20:55:19'}):
            self.assertTrue(codex_restart_required())

    def test_perform_handoff_blocks_until_codex_restarts_after_skill_sync(self) -> None:
        with patch('investor_council_shell.codex_bridge.skill_installed', return_value=True),              patch('investor_council_shell.codex_bridge._codex_installed', return_value=True),              patch('investor_council_shell.codex_bridge.codex_logged_in', return_value=True),              patch('investor_council_shell.codex_bridge.codex_restart_required', return_value=True):
            result = perform_handoff(
                mentor_name='Livermore',
                market_notes='index range',
                position='30%',
                symbol='ABC',
                question='What next?',
            )

        self.assertFalse(result['ok'])
        self.assertEqual(result['mode'], 'blocked')
        self.assertIn('Codex', result['message'])

    def test_backend_handoff_returns_safe_payload_when_bridge_raises(self) -> None:
        backend = InvestorCouncilBackend()
        with patch.object(backend, '_mentor_by_id', return_value={'id': 'livermore', 'status': 'ready', 'display_name_zh': 'Livermore'}),              patch('investor_council_shell.app.perform_handoff', side_effect=RuntimeError('boom')):
            result = backend.handoff({
                'mentor_id': 'livermore',
                'market_notes': 'index range',
                'position': '30%',
                'symbol': 'ABC',
                'question': 'What next?',
            })

        self.assertFalse(result['ok'])
        self.assertEqual(result['mode'], 'blocked')
        self.assertIn('boom', result['message'])
        self.assertIn('display_prompt', result)


if __name__ == '__main__':
    unittest.main()
