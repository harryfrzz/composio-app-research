"""Score agent passes against the hand-verified gold standard.

This is the highest-integrity accuracy check the brief asks for: agent answers
compared to fields a human read directly from official docs, not to a second LLM.
It scores the doc-objective fields (auth_methods as an exact set, api_surface.type
exactly) as the headline, and reports access_tier separately because it is a
documented judgment call rather than a single objective fact.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_agent.io_utils import load_result_map, read_json, write_json

OBJECTIVE_FIELDS = ["auth_methods", "api_surface_type"]


def load_pass(path: Path) -> dict[int, Any]:
    return load_result_map(path)


def score_field(field: str, agent_value: Any, gold_value: Any) -> bool:
    if field == "auth_methods":
        return sorted(agent_value) == sorted(gold_value)
    return agent_value == gold_value


def agent_field(result: Any, field: str) -> Any:
    if field == "auth_methods":
        return result.auth_methods
    if field == "api_surface_type":
        return result.api_surface.type
    if field == "access_tier":
        return result.access_tier
    raise KeyError(field)


def evaluate(pass_map: dict[int, Any], gold_apps: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for gold in gold_apps:
        result = pass_map.get(gold["id"])
        if result is None:
            continue
        for field in OBJECTIVE_FIELDS + ["access_tier"]:
            agent_value = agent_field(result, field)
            gold_value = gold["access_tier"] if field == "access_tier" else gold[field]
            rows.append(
                {
                    "id": gold["id"],
                    "app": gold["app"],
                    "field": field,
                    "agent": agent_value,
                    "gold": gold_value,
                    "correct": score_field(field, agent_value, gold_value),
                }
            )
    objective = [r for r in rows if r["field"] in OBJECTIVE_FIELDS]
    access = [r for r in rows if r["field"] == "access_tier"]

    def acc(subset: list[dict[str, Any]]) -> float:
        return round(sum(r["correct"] for r in subset) / len(subset), 4) if subset else 0.0

    return {
        "objective_accuracy": acc(objective),
        "access_tier_accuracy": acc(access),
        "auth_methods_accuracy": acc([r for r in rows if r["field"] == "auth_methods"]),
        "api_type_accuracy": acc([r for r in rows if r["field"] == "api_surface_type"]),
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score agent passes against the hand-verified gold set.")
    parser.add_argument("--gold", type=Path, default=Path("data/gold_standard.json"))
    parser.add_argument("--pass1", type=Path, default=Path("data/pass1_raw.jsonl"))
    parser.add_argument("--pass2", type=Path, default=Path("data/pass2_corrected.json"))
    parser.add_argument("--output", type=Path, default=Path("data/gold_accuracy.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gold = read_json(args.gold)["apps"]
    pass1 = load_pass(args.pass1)
    pass2 = load_pass(args.pass2)

    p1 = evaluate(pass1, gold)
    p2 = evaluate(pass2, gold)

    report = {
        "gold_size": len(gold),
        "methodology": (
            "Fields read by hand from official docs (see data/gold_standard.json sources). "
            "auth_methods scored as an exact set, api_surface.type scored exactly; these two form "
            "objective_accuracy. access_tier reported separately as a documented judgment call."
        ),
        "objective_accuracy": {"pass1": p1["objective_accuracy"], "pass2": p2["objective_accuracy"]},
        "auth_methods_accuracy": {"pass1": p1["auth_methods_accuracy"], "pass2": p2["auth_methods_accuracy"]},
        "api_type_accuracy": {"pass1": p1["api_type_accuracy"], "pass2": p2["api_type_accuracy"]},
        "access_tier_accuracy": {"pass1": p1["access_tier_accuracy"], "pass2": p2["access_tier_accuracy"]},
        "pass1_rows": p1["rows"],
        "pass2_rows": p2["rows"],
    }
    write_json(args.output, report)
    print(json.dumps({k: report[k] for k in (
        "gold_size", "objective_accuracy", "auth_methods_accuracy", "api_type_accuracy", "access_tier_accuracy"
    )}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        exit_code = 2
    raise SystemExit(exit_code)
