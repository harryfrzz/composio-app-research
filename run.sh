#!/usr/bin/env bash
#
# One-shot: run the entire research pipeline end to end.
#
#   ./run.sh          resume from committed checkpoints (cheap if already done)
#   ./run.sh --fresh  ignore checkpoints and regenerate everything (~600 paid calls)
#
# Needs COMPOSIO_API_KEY and OPENAI_API_KEY in .env (see .env.example).
#
set -euo pipefail
cd "$(dirname "$0")"

FORCE=""
[ "${1:-}" = "--fresh" ] && FORCE="--force"

# --- prerequisites -----------------------------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
  echo "→ Created .env from .env.example. Add COMPOSIO_API_KEY + OPENAI_API_KEY, then re-run."
  exit 1
fi
set -a; . ./.env; set +a
: "${COMPOSIO_API_KEY:?Set COMPOSIO_API_KEY in .env}"
: "${OPENAI_API_KEY:?Set OPENAI_API_KEY in .env}"
[ -f apps.json ] || { echo "✗ apps.json missing at repo root (the assignment's 100-app input)."; exit 1; }

# --- python env --------------------------------------------------------------
[ -d .venv ] || python3 -m venv .venv
PY=.venv/bin/python
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r requirements.txt

# --- pipeline ----------------------------------------------------------------
echo "[1/8] pass 1 — research all apps with Composio tools"
"$PY" research_agent/agent.py $FORCE

echo "[2/8] verify pass 1 — accuracy report + failure modes"
"$PY" research_agent/verify.py

echo "[3/8] pass 2 — corrected rerun on all apps (uses the failure modes above)"
"$PY" research_agent/agent.py --prompt-version pass2 --output data/pass2_full_raw.jsonl $FORCE

echo "[4/8] verify pass 2 — writes the canonical data/pass2_corrected.json"
"$PY" research_agent/verify.py --pass2 data/pass2_full_raw.jsonl

echo "[5/8] evidence-URL liveness gate (+patch human-review on dead links)"
"$PY" research_agent/check_evidence.py --input data/pass2_corrected.json --patch

echo "[6/8] hand-verified gold scoring (authoritative accuracy)"
"$PY" research_agent/score_gold.py

echo "[7/8] automation rollup — what ran automatically vs needed a human"
"$PY" research_agent/automation_report.py --results data/pass2_corrected.json

echo "[8/8] pattern analysis on the corrected dataset"
"$PY" analysis/patterns.py --input data/pass2_corrected.json

# --- refresh the web app's copy of the data ----------------------------------
dst=composio-assessment-result/public/data
if [ -d "$dst" ]; then
  echo "→ syncing outputs into the web app ($dst)"
  mkdir -p "$dst/traces"
  cp data/pass2_corrected.json data/accuracy_report.json data/verification_sample.json \
     data/gold_accuracy.json data/automation_report.json data/gold_standard.json \
     data/evidence_liveness.json "$dst"/
  cp analysis/patterns.json "$dst"/patterns.json
  cp data/traces/*.jsonl "$dst/traces"/ 2>/dev/null || true
fi

echo
echo "✓ Done. Data in data/ and analysis/ (frontend reads composio-assessment-result/public/data)."
echo "  View it:  cd composio-assessment-result && npm install && npm run dev"
