from __future__ import annotations

import unittest
from unittest.mock import patch

from investor_council_shell.app import InvestorCouncilBackend
from investor_council_shell.codex_bridge import perform_handoff


class HandoffResilienceTests(unittest.TestCase):
    def test_perform_handoff_uses_injection_path_without_crashing(self) -> None:
        with patch('investor_council_shell.codex_bridge.skill_installed', return_value=True), \
             patch('investor_council_shell.codex_bridge._codex_installed', return_value=True), \
             patch('investor_council_shell.codex_bridge.codex_logged_in', return_value=True), \
             patch('investor_council_shell.codex_bridge._copy_to_clipboard', return_value=True), \
             patch('investor_council_shell.codex_bridge._launch_codex', return_value=(True, 'ok')), \
             patch('investor_council_shell.codex_bridge.auto_injection_available', return_value=True), \
             patch('investor_council_shell.codex_bridge._inject_prompt', return_value=(True, '已自动发送。', 'existing_thread')):
            result = perform_handoff(
                mentor_name='利弗莫尔',
                market_notes='指数高位震荡',
                position='30% 仓位',
                symbol='光电股份',
                question='明天怎么办？',
            )

        self.assertTrue(result['ok'])
        self.assertEqual(result['mode'], 'auto_sent')
        self.assertEqual(result['thread_action'], 'existing_thread')

    def test_backend_handoff_returns_safe_payload_when_bridge_raises(self) -> None:
        backend = InvestorCouncilBackend()
        with patch.object(backend, '_mentor_by_id', return_value={'id': 'livermore', 'status': 'ready', 'display_name_zh': '利弗莫尔'}), \
             patch('investor_council_shell.app.perform_handoff', side_effect=RuntimeError('boom')):
            result = backend.handoff({
                'mentor_id': 'livermore',
                'market_notes': '指数高位震荡',
                'position': '30% 仓位',
                'symbol': '光电股份',
                'question': '明天怎么办？',
            })

        self.assertFalse(result['ok'])
        self.assertEqual(result['mode'], 'blocked')
        self.assertIn('交接异常', result['message'])
        self.assertIn('display_prompt', result)


if __name__ == '__main__':
    unittest.main()

