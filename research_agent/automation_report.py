"""Automated-vs-human summary.

The brief (section 3) asks to "log what the agent did automatically vs where it
needed a human." Per-app traces already record every tool call; this rolls them
up into one artifact: how much the agent did on its own (tool calls, rounds,
tokens, which Composio tools) and where it punted to a human (needs_human_review
plus a categorized reason). No LLM - pure aggregation over data/traces + results.
"""

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

from research_agent.io_utils import iter_jsonl, load_results, write_json

FINAL_TOOL_NAME = "record_app_research"

# Coarse buckets for free-text human_review_reason, so the report can say *why*
# a human was needed, not just how often.
REVIEW_REASON_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("gated_or_pricing_ambiguity", ("pric", "plan", "edition", "tier", "gat", "trial", "quota")),
    ("docs_unfetchable_or_js", ("render", "javascript", "js-", "load", "403", "404", "blocked", "inconsistent")),
    ("auth_inference", ("auth", "oauth", "token", "api key", "api-key", "scope")),
    ("mcp_uncertainty", ("mcp",)),
    ("evidence_gap", ("evidence", "url", "source", "quote", "absence", "inferred")),
]


def categorize_reason(reason: str) -> str:
    text = reason.lower()
    for label, markers in REVIEW_REASON_RULES:
        if any(marker in text for marker in markers):
            return label
    return "other" if text else "unspecified"


def find_trace(trace_dirs: list[Path], app_id: int) -> Path | None:
    name = f"{app_id:03d}.jsonl"
    for directory in trace_dirs:
        candidate = directory / name
        if candidate.exists():
            return candidate
    return None


def summarize_trace(path: Path) -> dict[str, Any]:
    rounds = 0
    tool_calls = 0
    tool_names: Counter[str] = Counter()
    validation_retries = 0
    stalls = 0
    prompt_tokens = 0
    completion_tokens = 0
    for event in iter_jsonl(path):
        kind = event.get("event")
        if kind == "model_response":
            rounds += 1
            usage = event.get("usage") or {}
            prompt_tokens += usage.get("prompt_tokens", 0) or 0
            completion_tokens += usage.get("completion_tokens", 0) or 0
        elif kind == "tool_calls_requested":
            for call in event.get("calls", []):
                if call.get("name") != FINAL_TOOL_NAME:
                    tool_calls += 1
                    tool_names[str(call.get("name"))] += 1
        elif kind == "final_validation_failed":
            validation_retries += 1
        elif kind == "no_tool_call":
            stalls += 1
    return {
        "rounds": rounds,
        "tool_calls": tool_calls,
        "distinct_tools": sorted(tool_names),
        "tool_call_counts": dict(tool_names),
        "validation_retries": validation_retries,
        "stalls": stalls,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Roll up automated-vs-human agent activity.")
    parser.add_argument("--results", type=Path, default=Path("data/pass1_raw.jsonl"))
    parser.add_argument(
        "--trace-dirs",
        default="data/traces,data/smoke_traces,data/smoke_retry_traces",
        help="Comma-separated trace directories, searched in order.",
    )
    parser.add_argument("--output", type=Path, default=Path("data/automation_report.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    trace_dirs = [Path(part.strip()) for part in args.trace_dirs.split(",") if part.strip()]
    results = load_results(args.results)

    per_app: list[dict[str, Any]] = []
    tool_usage: Counter[str] = Counter()
    total_tool_calls = 0
    total_rounds = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    traced = 0

    for result in results:
        trace_path = find_trace(trace_dirs, result.id)
        trace = summarize_trace(trace_path) if trace_path else {}
        if trace:
            traced += 1
            tool_usage.update(trace["tool_call_counts"])
            total_tool_calls += trace["tool_calls"]
            total_rounds += trace["rounds"]
            total_prompt_tokens += trace["prompt_tokens"]
            total_completion_tokens += trace["completion_tokens"]
        per_app.append(
            {
                "id": result.id,
                "app": result.app,
                "category": result.category,
                "fully_automated": not result.needs_human_review,
                "agent_confidence": result.agent_confidence,
                "needs_human_review": result.needs_human_review,
                "review_reason_category": (
                    categorize_reason(result.human_review_reason)
                    if result.needs_human_review
                    else None
                ),
                "trace_found": bool(trace),
                "rounds": trace.get("rounds"),
                "tool_calls": trace.get("tool_calls"),
                "distinct_tools": trace.get("distinct_tools"),
                "validation_retries": trace.get("validation_retries"),
            }
        )

    needed_human = [row for row in per_app if row["needs_human_review"]]
    reason_breakdown = Counter(row["review_reason_category"] for row in needed_human)

    report = {
        "total_apps": len(results),
        "traces_found": traced,
        "fully_automated_apps": sum(1 for row in per_app if row["fully_automated"]),
        "needed_human_apps": len(needed_human),
        "fully_automated_pct": round(
            100 * sum(1 for row in per_app if row["fully_automated"]) / len(results), 1
        )
        if results
        else 0.0,
        "human_review_reason_breakdown": dict(reason_breakdown.most_common()),
        "totals": {
            "tool_calls": total_tool_calls,
            "model_rounds": total_rounds,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
        },
        "averages_per_app": {
            "tool_calls": round(total_tool_calls / traced, 2) if traced else 0.0,
            "model_rounds": round(total_rounds / traced, 2) if traced else 0.0,
        },
        "composio_tool_usage": dict(tool_usage.most_common()),
        "per_app": per_app,
    }
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "total_apps": report["total_apps"],
                "fully_automated_apps": report["fully_automated_apps"],
                "needed_human_apps": report["needed_human_apps"],
                "fully_automated_pct": report["fully_automated_pct"],
                "avg_tool_calls_per_app": report["averages_per_app"]["tool_calls"],
                "composio_tool_usage": report["composio_tool_usage"],
                "human_review_reason_breakdown": report["human_review_reason_breakdown"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        exit_code = 2
    raise SystemExit(exit_code)
