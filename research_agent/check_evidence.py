"""Evidence-URL liveness gate.

The assignment makes "an evidence URL for every answer" non-negotiable, so a dead
evidence link is a real defect, not cosmetic. This script fetches every evidence
URL in a dataset, classifies it, and (with --patch) forces needs_human_review on
any row whose evidence includes a genuinely dead link. It uses no LLM: it is a
mechanical check that a human reviewer could rerun and reproduce exactly.

Classification:
- ok:      HTTP < 400 on HEAD or GET.
- blocked: 401/403/405/406/429 - the host refuses bots/HEAD but the page likely
           exists; not treated as a defect, only surfaced.
- dead:    404/410, other 4xx, any 5xx, or a network/DNS/timeout failure.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_agent.io_utils import load_results, write_json

BLOCKED_STATUSES = {401, 403, 405, 406, 429}


def require_requests() -> Any:
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'requests'. Install with: pip install -r requirements.txt"
        ) from exc
    return requests


def classify(status: int | None) -> str:
    if status is None:
        return "dead"  # network/DNS/timeout failure
    if status < 400:
        return "ok"
    if status in BLOCKED_STATUSES:
        return "blocked"
    return "dead"


def check_url(requests_mod: Any, url: str, timeout: int) -> dict[str, Any]:
    headers = {"User-Agent": "Mozilla/5.0 app-research-evidence-check/1.0"}
    status: int | None = None
    error = ""
    for method in ("HEAD", "GET"):
        try:
            response = requests_mod.request(
                method, url, headers=headers, timeout=timeout, allow_redirects=True
            )
            status = response.status_code
            # A 200 GET is authoritative; only fall through from HEAD if it failed.
            if status < 400 or method == "GET":
                break
        except Exception as exc:  # noqa: BLE001 - any transport failure means we could not confirm the page.
            error = f"{exc.__class__.__name__}: {exc}"
            status = None
    return {"url": url, "status_code": status, "verdict": classify(status), "error": error}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check evidence-URL liveness for a dataset.")
    parser.add_argument("--input", type=Path, default=Path("data/pass2_corrected.json"))
    parser.add_argument("--report-output", type=Path, default=Path("data/evidence_liveness.json"))
    parser.add_argument(
        "--patch",
        action="store_true",
        help="Force needs_human_review on rows with a dead evidence URL and write --patch-output.",
    )
    parser.add_argument("--patch-output", type=Path, default=Path("data/pass2_corrected.json"))
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=16)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    requests_mod = require_requests()
    results = load_results(args.input)

    unique_urls = sorted({url for result in results for url in result.evidence_urls})
    print(f"Checking {len(unique_urls)} unique evidence URLs from {len(results)} rows...")

    url_status: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        futures = {
            executor.submit(check_url, requests_mod, url, args.timeout): url for url in unique_urls
        }
        for future in concurrent.futures.as_completed(futures):
            record = future.result()
            url_status[record["url"]] = record

    verdict_counts: Counter[str] = Counter(record["verdict"] for record in url_status.values())

    per_row: list[dict[str, Any]] = []
    rows_with_dead: list[int] = []
    for result in results:
        verdicts = [url_status[url] for url in result.evidence_urls]
        dead = [record for record in verdicts if record["verdict"] == "dead"]
        blocked = [record for record in verdicts if record["verdict"] == "blocked"]
        ok = [record for record in verdicts if record["verdict"] == "ok"]
        if dead:
            rows_with_dead.append(result.id)
        per_row.append(
            {
                "id": result.id,
                "app": result.app,
                "evidence_count": len(result.evidence_urls),
                "ok": len(ok),
                "blocked": len(blocked),
                "dead": len(dead),
                "dead_urls": [record["url"] for record in dead],
                "has_live_evidence": bool(ok) or bool(blocked),
            }
        )

    report = {
        "input": str(args.input),
        "total_rows": len(results),
        "unique_urls_checked": len(unique_urls),
        "url_verdict_counts": dict(verdict_counts),
        "rows_with_dead_evidence": rows_with_dead,
        "rows_with_zero_live_evidence": [row["id"] for row in per_row if not row["has_live_evidence"]],
        "per_row": per_row,
        "url_status": url_status,
    }
    write_json(args.report_output, report)

    dead_total = verdict_counts.get("dead", 0)
    print(
        f"ok={verdict_counts.get('ok', 0)} blocked={verdict_counts.get('blocked', 0)} "
        f"dead={dead_total} ({dead_total}/{len(unique_urls)} urls). "
        f"{len(rows_with_dead)} rows have >=1 dead evidence URL."
    )

    if args.patch:
        patched = 0
        payload: list[dict[str, Any]] = []
        dead_by_id = {row["id"]: row["dead_urls"] for row in per_row if row["dead_urls"]}
        for result in results:
            row = result.model_dump(mode="json")
            dead_urls = dead_by_id.get(result.id)
            if dead_urls and not result.needs_human_review:
                row["needs_human_review"] = True
                note = f"Evidence liveness check found dead URL(s): {', '.join(dead_urls)}"
                row["human_review_reason"] = (
                    f"{result.human_review_reason} {note}".strip()
                    if result.human_review_reason
                    else note
                )
                patched += 1
            payload.append(row)
        write_json(args.patch_output, payload)
        print(f"Patched {patched} previously-unflagged row(s) with dead evidence -> {args.patch_output}")

    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        exit_code = 2
    raise SystemExit(exit_code)
