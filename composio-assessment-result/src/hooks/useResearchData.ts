import { useEffect, useState } from 'react';
import type {
  AccuracyReport,
  AppRecord,
  AutomationReport,
  EvidenceLiveness,
  GoldAccuracy,
  GoldStandard,
  Patterns,
  ResearchData,
  VerificationRow,
} from '../types/data';

// Client-side fetch of the raw static JSON (not a bundler import) so the data
// stays swappable and directly reachable at /data/*.json — which is also what
// makes it "easy for an agent to consume". BASE_URL keeps paths correct whether
// deployed at domain root or a repo subpath.
const base = import.meta.env.BASE_URL;

const DATA_URLS = {
  apps: `${base}data/pass2_corrected.json`,
  patterns: `${base}data/patterns.json`,
  accuracy: `${base}data/accuracy_report.json`,
  verification: `${base}data/verification_sample.json`,
  gold: `${base}data/gold_accuracy.json`,
  automation: `${base}data/automation_report.json`,
  goldStandard: `${base}data/gold_standard.json`,
  evidence: `${base}data/evidence_liveness.json`,
} as const;

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load ${url}: HTTP ${res.status}`);
  return (await res.json()) as T;
}

// Loud, minimal schema guards. We do not silently adapt to a different shape —
// if the data does not match, the page shows an error instead of guessing.
function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(`Schema check failed: ${message}`);
}

function validate(data: ResearchData): ResearchData {
  assert(Array.isArray(data.apps) && data.apps.length > 0, 'apps must be a non-empty array');
  const first = data.apps[0];
  assert(typeof first.app === 'string', 'app record missing "app"');
  assert(Array.isArray(first.auth_methods), 'app record missing "auth_methods"');
  assert(typeof first.access_tier === 'string', 'app record missing "access_tier"');
  assert(first.api_surface && typeof first.api_surface.type === 'string', 'app record missing api_surface.type');
  assert(Array.isArray(data.patterns.headline_findings), 'patterns missing headline_findings');
  assert(typeof data.accuracy.pass1_accuracy === 'number', 'accuracy missing pass1_accuracy');
  assert(Array.isArray(data.verification), 'verification must be an array');
  assert(typeof data.gold.objective_accuracy?.pass1 === 'number', 'gold missing objective_accuracy');
  assert(
    Array.isArray(data.goldStandard.apps) && data.goldStandard.apps.length > 0,
    'gold_standard missing apps',
  );
  assert(
    typeof data.evidence.unique_urls_checked === 'number',
    'evidence_liveness missing unique_urls_checked',
  );
  return data;
}

export interface LoadState {
  data: ResearchData | null;
  error: string | null;
  loading: boolean;
}

export function useResearchData(): LoadState {
  const [state, setState] = useState<LoadState>({ data: null, error: null, loading: true });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [apps, patterns, accuracy, verification, gold, automation, goldStandard, evidence] =
          await Promise.all([
            fetchJson<AppRecord[]>(DATA_URLS.apps),
            fetchJson<Patterns>(DATA_URLS.patterns),
            fetchJson<AccuracyReport>(DATA_URLS.accuracy),
            fetchJson<VerificationRow[]>(DATA_URLS.verification),
            fetchJson<GoldAccuracy>(DATA_URLS.gold),
            fetchJson<AutomationReport>(DATA_URLS.automation),
            fetchJson<GoldStandard>(DATA_URLS.goldStandard),
            fetchJson<EvidenceLiveness>(DATA_URLS.evidence),
          ]);
        const data = validate({
          apps,
          patterns,
          accuracy,
          verification,
          gold,
          automation,
          goldStandard,
          evidence,
        });
        if (!cancelled) setState({ data, error: null, loading: false });
      } catch (err) {
        if (!cancelled) {
          setState({ data: null, error: err instanceof Error ? err.message : String(err), loading: false });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
