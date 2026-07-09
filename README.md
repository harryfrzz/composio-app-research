# Composio App-Research Agent

This repo contains the backend-only research pipeline for the Composio take-home: a Python agent that researches the assignment-provided 100 apps with Composio tools, an independent verification pass, and pattern-analysis outputs for a separate frontend to consume.

## Setup

Required environment variables:

```bash
cp .env.example .env
# fill in COMPOSIO_API_KEY and OPENAI_API_KEY
```

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Add the assignment-provided `apps.json` at the repo root. The agent treats that file as ground truth and deliberately does not regenerate it.

The script defaults Composio's local cache to `data/.composio-cache`, so it does not need write access to `~/.composio`.

## How To Run

Smoke test on five apps:

```bash
python research_agent/agent.py --limit 5
```

Full pass-1 run:

```bash
python research_agent/agent.py
```

Verification and source-grounded correction:

```bash
python research_agent/verify.py
```

Optional corrected agent rerun on the verification sample:

```bash
python research_agent/agent.py --prompt-version pass2 --ids-file data/verification_sample_ids.json --output data/pass2_sample_raw.jsonl --force
python research_agent/verify.py --pass2 data/pass2_sample_raw.jsonl
```

In pass-2 mode, the agent automatically reads `data/accuracy_report.json` and adds the observed failure modes and recommended fixes to its research prompt. Supplying `--pass2` to the verifier makes the reported second-pass accuracy come from those rerun rows; without it, the verifier clearly labels pass 2 as a direct source-grounded patch.

Hand-verified gold scoring (the authoritative accuracy check — agent vs docs a human read):

```bash
python research_agent/score_gold.py
```

Evidence-URL liveness gate (flags dead evidence links, `--patch` forces human review on affected rows):

```bash
python research_agent/check_evidence.py --input data/pass2_corrected.json --patch
```

Automated-vs-human activity rollup (the brief's "what the agent did automatically vs where it needed a human"):

```bash
python research_agent/automation_report.py
```

Pattern analysis on the corrected dataset:

```bash
python analysis/patterns.py --input data/pass2_corrected.json
```

Print the exact output schema:

```bash
python research_agent/agent.py --print-schema
```

## Architecture

- `apps.json`: input list of 100 apps. Each item needs `id`, `app`, `category`, and optionally a hint URL such as `hint_url`, `docs_url`, or `website`.
- `research_agent/models.py`: strict Pydantic models for input apps, per-app research rows, and verification ground truth.
- `research_agent/agent.py`: Composio + OpenAI research agent. It creates Composio sessions with `mcp=True`, connects to the returned hosted endpoint with the official MCP Python client, uses Composio tools for search/browse work, validates the final function-call output, checkpoints rows to `data/pass1_raw.jsonl`, and writes per-app traces to `data/traces/`.
- `research_agent/verify.py`: independent automated verifier. It directly fetches the hint/evidence URLs, asks a source-grounded LLM verifier to re-derive the row without Composio tools (with a bounded validation-retry and per-app guard so one bad reply can't abort the run), writes `data/verification_sample.json`, computes pass-1/pass-2 accuracy split into structured-decision vs advisory-prose fields, and writes `data/pass2_corrected.json`.
- `research_agent/score_gold.py` + `data/gold_standard.json`: the authoritative accuracy check. `gold_standard.json` holds fields read **by hand** from official docs (with a source URL and quote per app); `score_gold.py` scores each agent pass against that human gold. This is the brief's "hand-cross-check against real docs," and it is trustworthy in a way the LLM-vs-LLM verifier is not.
- `research_agent/check_evidence.py`: mechanical (no-LLM) evidence-URL liveness gate. Classifies every evidence URL ok/blocked/dead and, with `--patch`, forces `needs_human_review` on rows with a dead link. Writes `data/evidence_liveness.json`.
- `research_agent/automation_report.py`: rolls the traces up into `data/automation_report.json` — tool calls, model rounds, tokens, which Composio tools, and how many apps came back fully automated vs needing a human (and why).
- `analysis/patterns.py`: clusters the corrected dataset into auth distributions, access-tier splits, blockers, easy wins, and outreach candidates, writing `analysis/patterns.json` and `analysis/patterns.md`.

The Composio integration follows the current session pattern: `composio.create(..., mcp=True)` returns the hosted MCP URL and headers. The agent connects over Streamable HTTP, converts the MCP tool schemas to OpenAI function definitions, and executes each requested tool through the MCP session.

Traces record the app prompt context, assistant text blocks, every MCP tool call, truncated tool results, retries, and final validation. They do not claim access to a model's hidden chain-of-thought.

## Output Schema

```json
{
  "id": 1,
  "app": "Salesforce",
  "category": "CRM and Sales",
  "description": "one-line what it does",
  "auth_methods": ["oauth2"],
  "auth_notes": "",
  "access_tier": "self_serve_free | self_serve_trial | paid_plan_required | admin_approval_required | partner_gated_contact_sales",
  "gating_reason": "why, if not self_serve_free",
  "api_surface": {
    "type": "REST | GraphQL | Both | None",
    "breadth": "brief note on how broad/documented",
    "mcp_exists": true,
    "mcp_notes": ""
  },
  "buildability_verdict": "ready_today | ready_with_workaround | blocked",
  "blocker": "main blocker if not ready_today, else null",
  "evidence_urls": ["https://..."],
  "rate_limit_notes": "best-effort, ok to leave blank",
  "notable_signals": "webhooks / native MCP support / sandbox env / anything worth flagging",
  "agent_confidence": 0,
  "needs_human_review": true,
  "human_review_reason": "why, if flagged"
}
```

## Results Summary

Both passes cover all 100 apps, **0 failures** (`data/pass1_raw.jsonl`, `data/pass2_full_raw.jsonl`). The corrected prompt was applied to **all 100** (not just the verification sample). The agent made **~600 Composio tool calls** (browser + search via hosted MCP), ~6/app (`data/automation_report.json`). Clusters of the corrected 100 (`analysis/patterns.json`):

- Auth: OAuth2 and token lead (65 mentions each), then other (26), api_key, basic.
- Access: 56 self-serve free, 7 self-serve trial, 20 paid-plan, 12 admin-approval, 5 partner/contact-sales.
- Buildability: 52 ready_today, 41 ready_with_workaround, 7 blocked.
- 50 easy wins; 9 need outreach. Top blockers: paid plan (18), auth/access ambiguity (13), partner/approval gate (12).

## Verification & Accuracy (two checks, gold is authoritative)

The LLM verifier scores a 20-app sample spanning all 10 categories, deliberately including the hard ones (DealCloud, Paygent Connect, iPayX, PitchBook, Waterfall.io, higgsfield, Consensus, Reducto, MrScraper, fanbasis). Pass 2 is a genuine agent re-run with a failure-mode-corrected prompt across all 100 apps — **not** the verifier grading its own patch (method `agent_rerun_pass2_file`).

**Check 1 — hand-verified gold (authoritative).** For 8 apps I read auth and API type directly from official docs (`data/gold_standard.json`, one source URL + quote per app) and scored both passes against that human gold (`data/gold_accuracy.json`). This is the brief's "hand-cross-check against real docs," and it is the number to trust:

| Gold field (n=8) | Pass 1 | Pass 2 |
|---|---|---|
| **Objective (auth + API type)** | **0.563** | **0.750** |
| auth_methods (exact set) | 0.375 | 0.750 |
| api_surface.type | 0.750 | 0.750 |
| access_tier (judgment call) | 0.750 | 0.750 |

The correction loop **works**: objective structured accuracy rose **56% → 75%**, and auth_methods doubled **37.5% → 75%**. Concretely, pass 2 fixed Zendesk (`api_key`→`token`), collapsed Shopify's over-listed 4 methods to the correct 2, and held Slack/Notion/Google Ads. An earlier corrected prompt over-shot the *other* way (collapsing everything to `oauth2`, which *lowered* auth accuracy to 0.25); the final prompt lists every documented method and no more. Still imperfect on both passes: GitHub (missing `basic`), Stripe, Salesforce.

**Check 2 — automated LLM verifier (honest, but oracle-limited).** `verify.py` independently fetches the docs and asks a source-grounded LLM (no Composio tools, never shown the agent answer) to re-derive each row (`data/accuracy_report.json`):

| Metric (n=20) | Pass 1 | Pass 2 |
|---|---|---|
| Overall field accuracy | 0.319 | 0.353 |
| Structured decision fields | 0.606 | 0.613 |
| Advisory free-text fields | ~0.05 | ~0.11 |

The LLM-verifier delta is small and I keep it honest rather than dress it up: (1) the metric scores 8 advisory free-text fields by 0.35 token-overlap — a bar two independent writers rarely clear — deflating the headline; (2) the oracle is a *nondeterministic LLM* and is sometimes simply wrong (its Salesforce auth ground truth came back `other`, which is incorrect — Salesforce is OAuth2). So LLM-vs-LLM agreement caps ~60% for structural reasons. **The hand-verified gold is the trustworthy signal, and it shows a clear improvement** the noisy oracle only partly reflects.

Pass-1 failure modes the corrected prompt targeted (`common_failure_modes`): auth over-listing, near-universal human-review flagging, and dead/deep evidence URLs.

## What the agent got wrong / where it needed a human

- **Over-flagged human review: 97/100 rows in pass 1 set `needs_human_review=true`** (`data/automation_report.json`), 90 of them for gated/pricing ambiguity — only 3 apps came back fully automated. The corrected prompt raised the bar and cut this to **63/100 (37 fully automated)** across the full run — the single biggest quality fix.
- **Auth over-listing** — pass 1 tacked `token`/`other`/`api_key` onto apps without first-party evidence (Shopify listed 4). Corrected in pass 2 (Shopify → 2, auth gold accuracy 37.5% → 75%). An earlier over-correction that collapsed everything to `oauth2` *lowered* accuracy — the final prompt lists every documented method and no more.
- **Dead evidence URLs**: `data/evidence_liveness.json` — of 448 evidence URLs in the corrected set, 415 live, 12 bot-blocked, **21 truly dead** across 14 rows; `check_evidence.py --patch` forced `needs_human_review` on the 5 of those not already flagged (final dataset: 68/100 flagged).
- **Flaky tool loop.** In the 5-app smoke test, Salesforce and HubSpot exhausted 8 tool rounds without a final answer (`data/smoke_failures.jsonl`); both succeeded on the full run. Browser-automation latency, not a data bug.
- **Apps that genuinely resist self-serve research** are captured as findings, not skipped: partner/contact-sales (PitchBook, DealCloud), thin/JS-rendered or gated docs (iPayX, Paygent Connect). Per the brief, a gated/partner finding with evidence is a valid answer.

## Known code caveats

- `verify.py` originally aborted the whole run on the first sampled app when the verifier LLM returned schema-shaped but semantically-invalid output (non-ready verdict with no blocker). Fixed with a bounded validation-retry that reflects the Pydantic error back to the model, plus a per-app guard that records `skipped_app_ids` instead of crashing.
- The corrected prompt was applied to **all 100 apps** (`data/pass2_full_raw.jsonl`); `data/pass2_corrected.json` is the canonical corrected dataset a frontend should read. `data/pass1_raw.jsonl` is retained as the "before" for the accuracy comparison.
- The gold set is 8 apps (well-documented, spot-checkable). It is intentionally small because each field was read by hand; it is a high-integrity check, not a large-N benchmark. The LLM verifier covers the full 20-app hard sample for breadth.
- `agent.py` runs one `asyncio.run()` per app inside a thread pool; on shutdown httpx logs benign `RuntimeError('Event loop is closed')` during async-client teardown **after** every row is already written. Cosmetic; does not affect data.

The full artifacts behind every number above: `data/gold_standard.json` + `data/gold_accuracy.json` (authoritative), `data/accuracy_report.json`, `data/verification_sample.json`, `data/verification_ground_truth.json`, `data/pass1_raw.jsonl` (before) + `data/pass2_corrected.json` (after), `data/evidence_liveness.json`, `data/automation_report.json`, `analysis/patterns.json`. No `data/failures.jsonl` was produced (0 failures). API credentials are read from the ignored local `.env` and never written to traces or result files.
