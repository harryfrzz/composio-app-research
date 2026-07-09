from __future__ import annotations

import unittest

from analysis.patterns import build_patterns
from research_agent.models import AppInput, AppResearchResult
from research_agent.verify import choose_sample


def result_row(
    app_id: int,
    app: str,
    category: str,
    access_tier: str = "self_serve_free",
    verdict: str = "ready_today",
    blocker: str | None = None,
) -> AppResearchResult:
    return AppResearchResult.model_validate(
        {
            "id": app_id,
            "app": app,
            "category": category,
            "description": f"{app} description.",
            "auth_methods": ["oauth2"],
            "auth_notes": "OAuth 2.0",
            "access_tier": access_tier,
            "gating_reason": "" if access_tier == "self_serve_free" else "Plan gate",
            "api_surface": {
                "type": "REST",
                "breadth": "Documented API",
                "mcp_exists": False,
                "mcp_notes": "",
            },
            "buildability_verdict": verdict,
            "blocker": blocker,
            "evidence_urls": [f"https://example.com/{app_id}"],
            "rate_limit_notes": "",
            "notable_signals": "webhooks",
            "agent_confidence": 90,
            "needs_human_review": False,
            "human_review_reason": "",
        }
    )


class PipelineTests(unittest.TestCase):
    def test_app_input_accepts_hint_alias(self) -> None:
        app = AppInput.model_validate(
            {
                "id": 1,
                "app": "Example",
                "category": "Test",
                "hint": "docs.example.com",
            }
        )
        self.assertEqual(app.hint_url, "https://docs.example.com")

    def test_schema_rejects_ready_today_with_blocker(self) -> None:
        with self.assertRaises(ValueError):
            result_row(1, "Example", "Category", blocker="Unexpected blocker")

    def test_sample_spans_all_categories(self) -> None:
        apps = [
            AppInput(id=index, app=f"App {index}", category=f"Category {(index - 1) % 10}")
            for index in range(1, 101)
        ]
        sample = choose_sample(apps, sample_size=20, hard_names=[])
        self.assertEqual(len(sample), 20)
        self.assertEqual(len({app.category for app in sample}), 10)

    def test_patterns_find_easy_wins_and_outreach(self) -> None:
        results = [
            result_row(1, "Easy", "CRM"),
            result_row(
                2,
                "Gated",
                "CRM",
                access_tier="partner_gated_contact_sales",
                verdict="blocked",
                blocker="Contact sales for partner API access",
            ),
        ]
        patterns = build_patterns(results)
        self.assertEqual([row["app"] for row in patterns["easy_wins"]], ["Easy"])
        self.assertEqual([row["app"] for row in patterns["needs_outreach"]], ["Gated"])


if __name__ == "__main__":
    unittest.main()
