# Composio App-Research Agent

A Python agent that researches 100 apps with Composio's SDK + hosted MCP — auth,
access tier, API surface, and a buildability verdict, with an evidence URL for
every answer — then verifies its own accuracy and clusters the findings. A small
React site presents the results.

**Live demo:** https://composio-app-research-bice.vercel.app
· **Source:** https://github.com/harryfrzz/composio-app-research

## Quick start

```bash
cp .env.example .env      # add COMPOSIO_API_KEY and OPENAI_API_KEY
./run.sh                  # runs the whole pipeline end to end
```

That's it. `./run.sh` sets up the Python venv, installs deps, and runs all eight
stages in order. It resumes from committed checkpoints, so a plain run is cheap.
To regenerate everything from scratch (~600 paid API calls):

```bash
./run.sh --fresh
```

Requires Python 3.10+. Uses `apps.json` at the repo root as the fixed input.

## What `run.sh` does

| # | Stage | Output |
|---|---|---|
| 1 | Research all apps (Composio tools) | `data/pass1_raw.jsonl`, `data/traces/` |
| 2 | Verify pass 1 → accuracy + failure modes | `data/accuracy_report.json` |
| 3 | Corrected pass 2 rerun (all apps) | `data/pass2_full_raw.jsonl` |
| 4 | Verify pass 2 → canonical dataset | `data/pass2_corrected.json` |
| 5 | Evidence-URL liveness gate | `data/evidence_liveness.json` |
| 6 | Hand-verified gold scoring | `data/gold_accuracy.json` |
| 7 | Automation rollup (agent vs human) | `data/automation_report.json` |
| 8 | Pattern analysis | `analysis/patterns.json`, `.md` |

Finally it copies the outputs into `composio-assessment-result/public/data/` so the
web app reflects the run.

## View the web app

```bash
cd composio-assessment-result
npm install
npm run dev
```

The site reads static JSON from `public/data/` — so an agent can consume the full
dataset by fetching those endpoints, no JavaScript required.

## Results

Both passes cover all 100 apps, **0 failures**. The corrected prompt was applied to
**all 100** (not just the sample), making ~600 Composio tool calls (~6/app).

**Accuracy — hand-verified gold (the number to trust).** For 8 apps, auth and API
type were read by hand from official docs (`data/gold_standard.json`, one source URL
+ quote each) and both passes scored against it:

| Gold field (n=8) | Pass 1 | Pass 2 |
|---|---|---|
| **Objective (auth + API type)** | **0.563** | **0.750** |
| auth_methods (exact set) | 0.375 | 0.750 |

The correction loop works: objective accuracy **56% → 75%**, auth_methods doubled.
A second, automated LLM verifier (`data/accuracy_report.json`, 20-app hard sample)
agrees directionally but caps low — it scores free-text by token overlap and the
oracle itself is noisy, so LLM-vs-LLM agreement tops out ~60%. Gold is authoritative.

**Clusters** (`analysis/patterns.json`): 56 self-serve free, 20 paid-plan, 12
admin-approval, 5 partner/contact-sales · 52 ready-today, 41 with-workaround, 7
blocked · 50 easy wins.

## Layout

- `research_agent/` — the agent (`agent.py`), verifier (`verify.py`), gold scorer
  (`score_gold.py`), evidence gate (`check_evidence.py`), automation rollup
  (`automation_report.py`), Pydantic models (`models.py`).
- `analysis/patterns.py` — clusters the corrected dataset.
- `composio-assessment-result/` — the React (Vite) results site.
- `data/` — all generated artifacts (checkpoints, traces, reports).

The Composio integration uses the current session pattern: `composio.create(..., mcp=True)`
returns a hosted MCP endpoint; the agent connects over Streamable HTTP, converts the
MCP tool schemas to OpenAI function definitions, and runs each tool through the session.
Traces record prompts, tool calls, truncated results, and final validation.

## Notes

- Credentials are read from the gitignored `.env` and never written to results.
  Full raw traces (`data/pass2_full_traces/`, gitignored) can capture secrets from
  scraped pages — scan before sharing.
- The gold set is intentionally small (8 apps, each read by hand) — a high-integrity
  check, not a large-N benchmark. The LLM verifier covers a 20-app sample for breadth.
- `data/pass2_corrected.json` is the canonical dataset a frontend should read;
  `data/pass1_raw.jsonl` is kept as the "before" for the accuracy comparison.
