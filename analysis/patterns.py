from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_agent.io_utils import load_results, write_json
from research_agent.models import AppResearchResult


def distribution(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def by_category_auth(results: list[AppResearchResult]) -> dict[str, dict[str, int]]:
    buckets: dict[str, Counter[str]] = defaultdict(Counter)
    for result in results:
        for method in result.auth_methods:
            buckets[result.category][method] += 1
    return {category: distribution(counter) for category, counter in sorted(buckets.items())}


def by_category_access(results: list[AppResearchResult]) -> dict[str, dict[str, int]]:
    buckets: dict[str, Counter[str]] = defaultdict(Counter)
    for result in results:
        buckets[result.category][result.access_tier] += 1
    return {category: distribution(counter) for category, counter in sorted(buckets.items())}


def normalize_blocker(blocker: str | None) -> str | None:
    if not blocker:
        return None
    text = blocker.lower()
    if any(marker in text for marker in ("partner", "sales", "contact", "approval")):
        return "partner/contact-sales or approval gate"
    if any(marker in text for marker in ("paid", "plan", "enterprise", "pricing")):
        return "paid plan required"
    if any(marker in text for marker in ("no api", "undocumented", "missing docs", "not public")):
        return "no public or complete API docs"
    if any(marker in text for marker in ("auth", "oauth", "token", "key")):
        return "auth/access setup ambiguity"
    if any(marker in text for marker in ("rate", "limit", "quota")):
        return "rate limit or quota concern"
    return blocker.strip()[:80]


def top_blockers(results: list[AppResearchResult]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    for result in results:
        blocker = normalize_blocker(result.blocker)
        if not blocker:
            continue
        counts[blocker] += 1
        if len(examples[blocker]) < 5:
            examples[blocker].append(result.app)
    return [
        {"blocker": blocker, "count": count, "example_apps": examples[blocker]}
        for blocker, count in counts.most_common(3)
    ]


def easy_wins(results: list[AppResearchResult]) -> list[dict[str, Any]]:
    rows = [
        {
            "id": result.id,
            "app": result.app,
            "category": result.category,
            "auth_methods": result.auth_methods,
            "api_surface_type": result.api_surface.type,
            "evidence_urls": result.evidence_urls,
        }
        for result in results
        if result.access_tier.startswith("self_serve_")
        and result.buildability_verdict == "ready_today"
        and not result.blocker
    ]
    return sorted(rows, key=lambda row: (row["category"], row["app"]))


def needs_outreach(results: list[AppResearchResult]) -> list[dict[str, Any]]:
    rows = []
    for result in results:
        blocker = (result.blocker or "").lower()
        if result.access_tier == "partner_gated_contact_sales" or any(
            marker in blocker for marker in ("partner", "sales", "contact")
        ):
            rows.append(
                {
                    "id": result.id,
                    "app": result.app,
                    "category": result.category,
                    "access_tier": result.access_tier,
                    "blocker": result.blocker,
                    "evidence_urls": result.evidence_urls,
                }
            )
    return sorted(rows, key=lambda row: (row["category"], row["app"]))


def headline_findings(patterns: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    auth_dist = patterns["auth_method_distribution"]["overall"]
    if auth_dist:
        top_auth, top_auth_count = next(iter(auth_dist.items()))
        findings.append(f"{top_auth} is the most common auth method ({top_auth_count} mentions).")
    access_dist = patterns["access_tier_distribution"]["overall"]
    gated_count = sum(
        count
        for tier, count in access_dist.items()
        if tier
        in {
            "paid_plan_required",
            "admin_approval_required",
            "partner_gated_contact_sales",
        }
    )
    findings.append(f"{gated_count} of {patterns['total_apps']} apps are gated beyond free/trial access.")
    if patterns["top_blockers"]:
        top = patterns["top_blockers"][0]
        findings.append(f"Top blocker: {top['blocker']} ({top['count']} apps).")
    findings.append(f"{len(patterns['easy_wins'])} apps look like easy toolkit wins.")
    findings.append(f"{len(patterns['needs_outreach'])} apps likely need outreach or partnership access.")
    return findings[:5]


def build_patterns(results: list[AppResearchResult]) -> dict[str, Any]:
    auth_counter: Counter[str] = Counter()
    for result in results:
        auth_counter.update(result.auth_methods)
    access_counter = Counter(result.access_tier for result in results)
    verdict_counter = Counter(result.buildability_verdict for result in results)
    review_counter = Counter("needs_review" if result.needs_human_review else "agent_verified" for result in results)

    patterns: dict[str, Any] = {
        "total_apps": len(results),
        "auth_method_distribution": {
            "overall": distribution(auth_counter),
            "by_category": by_category_auth(results),
        },
        "access_tier_distribution": {
            "overall": distribution(access_counter),
            "by_category": by_category_access(results),
        },
        "buildability_distribution": distribution(verdict_counter),
        "human_review_distribution": distribution(review_counter),
        "top_blockers": top_blockers(results),
        "easy_wins": easy_wins(results),
        "needs_outreach": needs_outreach(results),
    }
    patterns["headline_findings"] = headline_findings(patterns)
    return patterns


def markdown_summary(patterns: dict[str, Any]) -> str:
    lines = ["# App Research Patterns", ""]
    lines.extend(f"- {finding}" for finding in patterns["headline_findings"])
    lines.extend(["", "## Auth Method Distribution", ""])
    lines.extend(f"- {method}: {count}" for method, count in patterns["auth_method_distribution"]["overall"].items())
    lines.extend(["", "## Access Tier Distribution", ""])
    lines.extend(f"- {tier}: {count}" for tier, count in patterns["access_tier_distribution"]["overall"].items())
    lines.extend(["", "## Top Blockers", ""])
    if patterns["top_blockers"]:
        for blocker in patterns["top_blockers"]:
            examples = ", ".join(blocker["example_apps"])
            lines.append(f"- {blocker['blocker']}: {blocker['count']} apps ({examples})")
    else:
        lines.append("- No blockers recorded.")
    lines.extend(["", "## Easy Wins", ""])
    if patterns["easy_wins"]:
        lines.extend(f"- {row['app']} ({row['category']})" for row in patterns["easy_wins"])
    else:
        lines.append("- None found.")
    lines.extend(["", "## Needs Outreach", ""])
    if patterns["needs_outreach"]:
        lines.extend(f"- {row['app']} ({row['category']}): {row['blocker']}" for row in patterns["needs_outreach"])
    else:
        lines.append("- None found.")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate clustered pattern analysis.")
    parser.add_argument("--input", type=Path, default=Path("data/pass2_corrected.json"))
    parser.add_argument("--output-json", type=Path, default=Path("analysis/patterns.json"))
    parser.add_argument("--output-md", type=Path, default=Path("analysis/patterns.md"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = load_results(args.input)
    patterns = build_patterns(results)
    write_json(args.output_json, patterns)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown_summary(patterns), encoding="utf-8")
    print(json.dumps(patterns["headline_findings"], indent=2))
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        exit_code = 2
    raise SystemExit(exit_code)
