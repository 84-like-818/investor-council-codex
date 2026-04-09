from __future__ import annotations

import unittest
from unittest.mock import patch

from investor_council_shell.app import InvestorCouncilBackend


class InvestorCouncilBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = InvestorCouncilBackend()

    def test_public_handoff_result_hides_internal_prompt(self) -> None:
        result = {
            "ok": True,
            "prompt": "Use $investor-council。内部提示词",
            "mentor_name": "利弗莫尔",
            "market_notes": "指数高位震荡",
            "position": "30% 仓位",
            "symbol": "光电股份",
            "question": "明天怎么办？",
        }
        public_result = self.backend._public_handoff_result(result)
        self.assertNotIn("prompt", public_result)
        self.assertIn("display_prompt", public_result)
        self.assertIn("利弗莫尔", public_result["display_prompt"])
        self.assertNotIn("Use $investor-council", public_result["display_prompt"])

    def test_sanitize_history_item_hides_internal_prompt(self) -> None:
        item = {
            "mentor_name": "巴菲特",
            "market_notes": "市场恐慌",
            "position": "50% 仓位",
            "symbol": "苹果",
            "question": "该不该继续持有？",
            "prompt": "Use $investor-council。不要出现在前台界面",
        }
        sanitized = self.backend._sanitize_history_item(item)
        self.assertNotIn("prompt", sanitized)
        self.assertIn("display_prompt", sanitized)
        self.assertIn("巴菲特", sanitized["display_prompt"])

    @patch("investor_council_shell.app.runtime_status")
    def test_bootstrap_never_exposes_bootstrap_prompt(self, runtime_status_mock) -> None:
        runtime_status_mock.return_value = {
            "codex_installed": True,
            "codex_logged_in": True,
            "codex_running": False,
            "skill_installed": True,
            "auto_injection_available": True,
            "codex_launch_ready": True,
            "launch_source": "test",
            "launch_type": "exe",
            "thread_policy": "mentor_dedicated_threads",
            "product_home_writable": True,
            "webview_ready": True,
            "market_data_ready": True,
            "market_data_warn": False,
            "blocking": False,
            "blocking_message": "",
            "blocking_action": "",
            "ready_for_handoff": True,
            "repair_available": True,
            "checks": [],
        }
        payload = self.backend.bootstrap()
        self.assertNotIn("bootstrap_prompt", payload)
        self.assertIn("distribution", payload)
        self.assertEqual(payload["distribution"]["channel"], "GitHub Releases")
        self.assertIn("notice_center", payload)
        self.assertIn("prerequisites", payload["notice_center"])
        self.assertIn("risk", payload["notice_center"])
        self.assertIn("privacy", payload["notice_center"])


if __name__ == "__main__":
    unittest.main()

