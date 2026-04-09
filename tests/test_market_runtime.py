from __future__ import annotations

import sys
import unittest
from pathlib import Path

from investor_council_shell.codex_bridge import build_prompt, thread_title_for_mentor

ROOT = Path(__file__).resolve().parents[1]
MARKET_SCRIPTS = ROOT / "codex-skills" / "investor-council" / "scripts"
if str(MARKET_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(MARKET_SCRIPTS))

from market_data_client import MarketDataClient  # type: ignore  # noqa: E402


class MarketRuntimeTests(unittest.TestCase):
    def test_eastmoney_secid_market_detection(self) -> None:
        self.assertEqual(MarketDataClient._eastmoney_secid("600519"), "1.600519")
        self.assertEqual(MarketDataClient._eastmoney_secid("002594"), "0.002594")

    def test_prompt_contains_structured_fields(self) -> None:
        prompt = build_prompt(
            mentor_name="利弗莫尔",
            market_notes="指数高位震荡",
            position="30% 仓位",
            symbol="光电股份",
            question="明天怎么操作？",
        )
        self.assertIn("Use $investor-council", prompt)
        self.assertIn(thread_title_for_mentor("利弗莫尔"), prompt)
        self.assertIn("市场背景：指数高位震荡", prompt)
        self.assertIn("当前仓位：30% 仓位", prompt)


if __name__ == "__main__":
    unittest.main()
