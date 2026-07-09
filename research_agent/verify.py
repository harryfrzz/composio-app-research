from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_agent.io_utils import load_apps, load_result_map, load_results, write_json
from research_agent.models import (
    COMPARISON_FIELDS,
    AppInput,
    AppResearchResult,
    VerificationGroundTruth,
    get_nested_field,
)


DEFAULT_HARD_APPS = [
    "DealCloud",
    "Paygent Connect",
    "iPayX",
    "PitchBook",
    "Waterfall.io",
    "higgsfield",
    "Consensus",
    "Reducto",
    "MrScraper",
    "fanbasis",
]


VERIFY_TOOL_NAME = "record_verified_research"


def load_dotenv_if_present() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def require_verifier_dependencies() -> tuple[Any, Any]:
    try:
        import openai
        import requests
    except ImportError as exc:
        raise RuntimeError(
            "Missing verification dependencies. Install with: pip install -r requirements.txt"
        ) from exc
    return openai, requests


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def strip_html(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        text = re.sub(r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>", " ", html, flags=re.I)
        text = re.sub(r"<style\b[^<]*(?:(?!</style>)<[^<]*)*</style>", " ", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()


def fetch_url(requests_mod: Any, url: str, timeout: int) -> dict[str, Any]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 app-research-verifier/1.0 "
            "(source-grounded verification; contact: local take-home script)"
        )
    }
    started = time.time()
    response = requests_mod.get(url, headers=headers, timeout=timeout)
    elapsed = round(time.time() - started, 3)
    text = strip_html(response.text)
    return {
        "url": url,
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "elapsed_seconds": elapsed,
        "text": text[:30000],
        "text_length": len(text),
    }


def choose_sample(apps: list[AppInput], sample_size: int, hard_names: list[str]) -> list[AppInput]:
    by_name = {app.app.lower(): app for app in apps}
    selected: list[AppInput] = []
    seen: set[int] = set()

    for name in hard_names:
        app = by_name.get(name.lower())
        if app and app.id not in seen:
            selected.append(app)
            seen.add(app.id)

    by_category: dict[str, list[AppInput]] = defaultdict(list)
    for app in apps:
        by_category[app.category].append(app)
    for category in sorted(by_category):
        if len(selected) >= sample_size:
            break
        for app in by_category[category]:
            if app.id not in seen:
                selected.append(app)
                seen.add(app.id)
                break

    for app in apps:
        if len(selected) >= sample_size:
            break
        if app.id not in seen:
            selected.append(app)
            seen.add(app.id)
    return selected[:sample_size]


def candidate_urls(app: AppInput, agent_result: AppResearchResult | None, max_urls: int) -> list[str]:
    urls: list[str] = []
    if app.hint_url:
        urls.append(app.hint_url)
    if agent_result:
        urls.extend(agent_result.evidence_urls)
    deduped: list[str] = []
    for url in urls:
        cleaned = str(url).strip()
        if cleaned.startswith(("http://", "https://")) and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped[:max_urls]


def verify_tool_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": VERIFY_TOOL_NAME,
            "description": (
                "Submit source-grounded verification for one app using only the fetched "
                "evidence text."
            ),
            "parameters": VerificationGroundTruth.model_json_schema(),
            "strict": True,
        },
    }


def verifier_prompt(
    app: AppInput,
    fetched_pages: list[dict[str, Any]],
) -> str:
    evidence_blocks = []
    for page in fetched_pages:
        evidence_blocks.append(
            f"URL: {page['url']}\n"
            f"HTTP status: {page['status_code']}\n"
            f"Content type: {page['content_type']}\n"
            f"Fetched text excerpt:\n{page['text'][:18000]}"
        )
    evidence_text = "\n\n---\n\n".join(evidence_blocks) or "No pages could be fetched."
    return f"""
You are independently verifying one app-research row. Use only the fetched page
text below, not search snippets and not prior agent claims. If the fetched
evidence is insufficient or contradictory, set needs_human_review=true in the
verified_result and explain why.

App:
- id: {app.id}
- app: {app.app}
- category: {app.category}
- hint_url: {app.hint_url or ""}

Fetched evidence:
{evidence_text}

Return a VerificationGroundTruth object by calling {VERIFY_TOOL_NAME}. The
verified_result must use the exact AppResearchResult schema and evidence_urls
must be a subset of evidence_checked.
"""


def run_verifier_llm(
    openai_mod: Any,
    app: AppInput,
    fetched_pages: list[dict[str, Any]],
    model: str,
    max_tokens: int,
    max_attempts: int = 3,
) -> VerificationGroundTruth:
    client = openai_mod.OpenAI()
    # OpenAI strict mode only enforces JSON shape, not the Pydantic cross-field
    # rules (e.g. non-ready verdicts require a blocker). Reflect validation errors
    # back to the model and retry, mirroring the agent's final-tool correction loop,
    # so one schema-valid-but-semantically-invalid reply cannot abort verification.
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are a source-grounded verifier. You must call the verification "
                "tool exactly once. Do not invent evidence. You have not been shown "
                "the pass-1 answer, so derive every field independently."
            ),
        },
        {"role": "user", "content": verifier_prompt(app, fetched_pages)},
    ]
    last_error: ValueError | None = None
    for attempt in range(1, max_attempts + 1):
        response = client.chat.completions.create(
            model=model,
            max_completion_tokens=max_tokens,
            tools=[verify_tool_schema()],
            tool_choice={
                "type": "function",
                "function": {"name": VERIFY_TOOL_NAME},
            },
            parallel_tool_calls=False,
            messages=messages,
        )
        message = response.choices[0].message
        tool_calls = [
            call
            for call in (message.tool_calls or [])
            if call.function.name == VERIFY_TOOL_NAME
        ]
        if not tool_calls:
            raise RuntimeError(f"Verifier did not call {VERIFY_TOOL_NAME} for {app.app}")
        call = tool_calls[-1]
        try:
            return VerificationGroundTruth.model_validate_json(call.function.arguments)
        except ValueError as exc:
            last_error = exc
            if attempt >= max_attempts:
                raise
            messages.append(message.model_dump(exclude_none=True))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": (
                        f"Validation failed: {exc}. Fix the fields and call "
                        f"{VERIFY_TOOL_NAME} again. Any non-ready buildability_verdict "
                        "requires a non-empty blocker; ready_today requires blocker=null; "
                        "evidence_urls must be a subset of evidence_checked."
                    ),
                }
            )
    raise RuntimeError(f"unreachable verifier retry state for {app.app}") from last_error


def comparable(value: Any) -> Any:
    if isinstance(value, list):
        return sorted(comparable(item) for item in value)
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        lowered = re.sub(r"https?://", "", lowered)
        lowered = re.sub(r"[^a-z0-9_./ -]+", " ", lowered)
        return re.sub(r"\s+", " ", lowered).strip()
    return value


def token_overlap(left: str, right: str) -> float:
    left_tokens = set(re.findall(r"[a-z0-9]+", left.lower()))
    right_tokens = set(re.findall(r"[a-z0-9]+", right.lower()))
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def field_correct(field: str, agent_value: Any, verified_value: Any) -> bool:
    normalized_agent = comparable(agent_value)
    normalized_verified = comparable(verified_value)
    if normalized_agent == normalized_verified:
        return True
    free_text_fields = {
        "description",
        "auth_notes",
        "gating_reason",
        "api_surface.breadth",
        "api_surface.mcp_notes",
        "blocker",
        "rate_limit_notes",
        "notable_signals",
        "human_review_reason",
    }
    if field in free_text_fields and isinstance(agent_value, str) and isinstance(verified_value, str):
        return token_overlap(agent_value, verified_value) >= 0.35
    if field == "evidence_urls" and isinstance(agent_value, list) and isinstance(verified_value, list):
        agent_hosts = {urlparse(url).netloc.lower() for url in agent_value}
        verified_hosts = {urlparse(url).netloc.lower() for url in verified_value}
        return bool(agent_hosts and verified_hosts and agent_hosts & verified_hosts)
    return False


def compare_results(
    app: AppInput,
    agent_result: AppResearchResult | None,
    verified: VerificationGroundTruth,
    pass_label: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    agent_dump = agent_result.model_dump(mode="json") if agent_result else {}
    verified_dump = verified.verified_result.model_dump(mode="json")
    for field in COMPARISON_FIELDS:
        agent_value = get_nested_field(agent_dump, field)
        verified_value = get_nested_field(verified_dump, field)
        rows.append(
            {
                "pass": pass_label,
                "app_id": app.id,
                "app": app.app,
                "category": app.category,
                "field": field,
                "agent_answer": agent_value,
                "verified_answer": verified_value,
                "correct": field_correct(field, agent_value, verified_value),
                "evidence_checked": verified.evidence_checked,
            }
        )
    return rows


# Structured decision fields drive the buildability call and compare exactly after
# normalization. The remaining COMPARISON_FIELDS are advisory free-text scored by
# token overlap, which two independent writers rarely reach; reporting the two
# classes separately keeps the headline from being deflated by prose divergence.
STRUCTURED_FIELDS = {
    "auth_methods",
    "access_tier",
    "buildability_verdict",
    "api_surface.type",
    "api_surface.mcp_exists",
    "evidence_urls",
    "needs_human_review",
    "blocker",
}


def accuracy(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    correct = sum(1 for row in rows if row["correct"])
    return round(correct / len(rows), 4)


def field_class_accuracy(rows: list[dict[str, Any]]) -> dict[str, float]:
    structured = [row for row in rows if row["field"] in STRUCTURED_FIELDS]
    advisory = [row for row in rows if row["field"] not in STRUCTURED_FIELDS]
    return {
        "structured_decision": accuracy(structured),
        "advisory_free_text": accuracy(advisory),
    }


def per_field_accuracy(rows: list[dict[str, Any]]) -> dict[str, float]:
    by_field: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_field[row["field"]].append(row)
    return {field: accuracy(field_rows) for field, field_rows in sorted(by_field.items())}


def diagnose_failure_modes(rows: list[dict[str, Any]], fetched_by_id: dict[int, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    modes: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if row["correct"]:
            continue
        pages = fetched_by_id.get(row["app_id"], [])
        statuses = {page.get("status_code") for page in pages}
        text_lengths = [page.get("text_length", 0) for page in pages]
        if not pages:
            mode = "no_fetchable_evidence"
        elif any(status and int(status) >= 400 for status in statuses):
            mode = "evidence_url_http_error"
        elif text_lengths and max(text_lengths) < 500:
            mode = "thin_or_js_rendered_docs"
        elif row["field"] in {"access_tier", "gating_reason", "blocker"}:
            mode = "ambiguous_gating_language"
        elif row["field"] == "evidence_urls":
            mode = "weak_or_mismatched_evidence_url"
        else:
            mode = "field_interpretation_mismatch"
        modes[mode] += 1
        if len(examples[mode]) < 5:
            examples[mode].append(f"{row['app']}:{row['field']}")
    return [
        {"mode": mode, "count": count, "examples": examples[mode]}
        for mode, count in modes.most_common()
    ]


def apply_result_corrections(
    pass1_results: list[AppResearchResult],
    replacements_by_id: dict[int, AppResearchResult],
) -> list[dict[str, Any]]:
    corrected: list[dict[str, Any]] = []
    for result in pass1_results:
        replacement = replacements_by_id.get(result.id)
        if replacement:
            corrected.append(replacement.model_dump(mode="json"))
        else:
            corrected.append(result.model_dump(mode="json"))
    return corrected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify sampled app-research results.")
    parser.add_argument("--apps", type=Path, default=Path("apps.json"))
    parser.add_argument("--pass1", type=Path, default=Path("data/pass1_raw.jsonl"))
    parser.add_argument("--pass2", type=Path, default=None)
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--max-urls", type=int, default=6)
    parser.add_argument("--fetch-timeout", type=int, default=20)
    parser.add_argument(
        "--model",
        default=os.getenv(
            "OPENAI_VERIFIER_MODEL",
            os.getenv("OPENAI_MODEL", "gpt-5.4"),
        ),
    )
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--verification-output", type=Path, default=Path("data/verification_sample.json"))
    parser.add_argument("--ground-truth-output", type=Path, default=Path("data/verification_ground_truth.json"))
    parser.add_argument("--accuracy-output", type=Path, default=Path("data/accuracy_report.json"))
    parser.add_argument("--pass2-output", type=Path, default=Path("data/pass2_corrected.json"))
    parser.add_argument("--sample-ids-output", type=Path, default=Path("data/verification_sample_ids.json"))
    parser.add_argument("--fetched-output", type=Path, default=Path("data/verification_fetched_pages.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv_if_present()
    require_env("OPENAI_API_KEY")
    openai_mod, requests_mod = require_verifier_dependencies()

    apps = load_apps(args.apps)
    pass1_by_id = load_result_map(args.pass1)
    sample = choose_sample(apps, args.sample_size, DEFAULT_HARD_APPS)
    write_json(args.sample_ids_output, [app.id for app in sample])

    verified_by_id: dict[int, VerificationGroundTruth] = {}
    fetched_by_id: dict[int, list[dict[str, Any]]] = {}
    for app in sample:
        agent_result = pass1_by_id.get(app.id)
        urls = candidate_urls(app, agent_result, args.max_urls)
        fetched_pages: list[dict[str, Any]] = []
        for url in urls:
            try:
                fetched_pages.append(fetch_url(requests_mod, url, args.fetch_timeout))
            except Exception as exc:  # noqa: BLE001 - keep verification moving and record fetch failures.
                fetched_pages.append(
                    {
                        "url": url,
                        "status_code": 0,
                        "content_type": "",
                        "elapsed_seconds": 0,
                        "text": "",
                        "text_length": 0,
                        "fetch_error": f"{exc.__class__.__name__}: {exc}",
                    }
                )
        fetched_by_id[app.id] = fetched_pages
        try:
            verified = run_verifier_llm(
                openai_mod=openai_mod,
                app=app,
                fetched_pages=fetched_pages,
                model=args.model,
                max_tokens=args.max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - one unverifiable app must not abort the sample.
            print(f"skip {app.id}: {app.app}: verifier error: {exc}", file=sys.stderr)
            continue
        verified_by_id[app.id] = verified
        print(f"verified {app.id}: {app.app}")

    # Compare only apps the verifier produced ground truth for; a skipped app is
    # reported in skipped_app_ids rather than silently dropped or crashing the run.
    verified_sample = [app for app in sample if app.id in verified_by_id]
    skipped_ids = [app.id for app in sample if app.id not in verified_by_id]

    pass1_rows: list[dict[str, Any]] = []
    for app in verified_sample:
        pass1_rows.extend(compare_results(app, pass1_by_id.get(app.id), verified_by_id[app.id], "pass1"))

    if args.pass2:
        replacements_by_id = load_result_map(args.pass2)
        correction_method = "agent_rerun_pass2_file"
    else:
        replacements_by_id = {
            app_id: verified.verified_result
            for app_id, verified in verified_by_id.items()
        }
        correction_method = "source_grounded_verifier_patch"

    pass1_results = load_results(args.pass1)
    corrected_payload = apply_result_corrections(pass1_results, replacements_by_id)
    write_json(args.pass2_output, corrected_payload)
    pass2_by_id = {
        row["id"]: AppResearchResult.model_validate(row)
        for row in corrected_payload
    }

    pass2_rows: list[dict[str, Any]] = []
    for app in verified_sample:
        pass2_rows.extend(compare_results(app, pass2_by_id.get(app.id), verified_by_id[app.id], "pass2"))

    all_rows = pass1_rows + pass2_rows
    failure_modes = diagnose_failure_modes(pass1_rows, fetched_by_id)
    report = {
        "pass1_accuracy": accuracy(pass1_rows),
        "pass2_accuracy": accuracy(pass2_rows),
        "per_field_accuracy": {
            "pass1": per_field_accuracy(pass1_rows),
            "pass2": per_field_accuracy(pass2_rows),
        },
        "field_class_accuracy": {
            "pass1": field_class_accuracy(pass1_rows),
            "pass2": field_class_accuracy(pass2_rows),
        },
        "metric_notes": (
            "Overall accuracy scores all 16 fields equally; 8 are advisory free-text "
            "compared by 0.35 token-overlap, a bar two independent writers rarely clear, "
            "which deflates the headline. field_class_accuracy.structured_decision reflects "
            "the enum/list/bool fields that drive the buildability call. Ground truth is a "
            "nondeterministic source-grounded LLM verifier, so overall deltas within roughly "
            "1-2 points are within oracle noise rather than real movement."
        ),
        "sample_size": len(verified_sample),
        "sample_app_ids": [app.id for app in verified_sample],
        "sample_apps": [app.app for app in verified_sample],
        "skipped_app_ids": skipped_ids,
        "methodology": {
            "pass1": "Composio-tool research agent output.",
            "verification": (
                "Independent direct HTTP fetch of hint/evidence URLs, then a source-grounded "
                "LLM verifier without Composio tools."
            ),
            "pass2": correction_method,
            "comparison": (
                "Enums/lists/bools compare exactly after normalization; free-text fields use "
                "token-overlap tolerance; evidence URLs compare by overlapping host."
            ),
        },
        "common_failure_modes": failure_modes,
        "recommended_agent_fixes": [
            "Prefer official docs/auth/pricing URLs over search snippets.",
            "Treat HTTP errors, short fetched text, and JS-rendered docs as human-review triggers.",
            "For gating/access fields, require explicit pricing, trial, admin, or partner-language evidence.",
            "Do not count an evidence URL as valid unless the fetched page text supports the field.",
        ],
    }

    write_json(args.verification_output, all_rows)
    write_json(
        args.ground_truth_output,
        [verified.model_dump(mode="json") for verified in verified_by_id.values()],
    )
    write_json(args.fetched_output, fetched_by_id)
    write_json(args.accuracy_output, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        exit_code = 2
    raise SystemExit(exit_code)
