#!/usr/bin/env python3
"""Warnings for unresolved cards, source failures, and a stale scrape."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import refresh_alert  # noqa: E402


NOW = datetime(2026, 10, 25, 18, 0, tzinfo=timezone.utc)


class RefreshAlertTests(unittest.TestCase):
    def test_unresolved_source_failure_and_stale_success(self):
        warnings = refresh_alert.collect_warnings(
            {
                "checked_at": "2026-10-25T17:00:00Z",
                "last_success": {"web": "2026-10-23T16:00:00Z"},
                "failures": [{"source": "youtube", "error": "timeout"}],
            },
            {"unresolved": ["UE99BT/X-1-001"], "ok": False},
            NOW,
        )
        self.assertTrue(any(line.startswith("Unresolved cards: UE99BT/X-1-001") for line in warnings))
        self.assertTrue(any("Source failed: youtube: timeout" in line for line in warnings))
        self.assertTrue(any("No source has succeeded in 48 hours" in line for line in warnings))

    def test_missing_check_does_not_warn_that_the_scrape_is_stale(self):
        warnings = refresh_alert.collect_warnings(
            {"failures": [{"source": "web", "error": "down"}]},
            {"unresolved": ["UE99BT/X-1-001"]},
            NOW,
        )
        self.assertEqual(
            warnings,
            ["Unresolved cards: UE99BT/X-1-001", "Source failed: web: down"],
        )

    def test_stale_only_ignores_cards_and_source_failures(self):
        warnings = refresh_alert.collect_warnings(
            {
                "checked_at": "2026-10-25T17:00:00Z",
                "last_success": {"web": "2026-10-25T12:00:00Z"},
                "failures": [{"source": "youtube", "error": "timeout"}],
            },
            {"unresolved": ["UE99BT/X-1-001"]},
            NOW,
            stale_only=True,
        )
        self.assertEqual(warnings, [])

    def test_recent_success_is_not_stale(self):
        warnings = refresh_alert.collect_warnings(
            {
                "checked_at": "2026-10-25T17:00:00Z",
                "last_success": {"youtube": "2026-10-25T12:00:00Z"},
                "failures": [],
            },
            {"ok": True, "unresolved": []},
            NOW,
        )
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
