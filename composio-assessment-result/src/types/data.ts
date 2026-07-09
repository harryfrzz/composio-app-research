// Single source of truth for the research-data schema. Every component imports
// from here — no ad-hoc re-typing of the shape. Mirrors the JSON emitted by the
// research agent (see public/data/*.json).

export type AuthMethod = 'oauth2' | 'api_key' | 'basic' | 'token' | 'other';

export type AccessTier =
  | 'self_serve_free'
  | 'self_serve_trial'
  | 'paid_plan_required'
  | 'admin_approval_required'
  | 'partner_gated_contact_sales';

export type ApiType = 'REST' | 'GraphQL' | 'Both' | 'None';

export type Verdict = 'ready_today' | 'ready_with_workaround' | 'blocked';

export interface ApiSurface {
  type: ApiType;
  breadth: string;
  mcp_exists: boolean;
  mcp_notes: string;
}

export interface AppRecord {
  id: number;
  app: string;
  category: string;
  description: string;
  auth_methods: AuthMethod[];
  auth_notes: string;
  access_tier: AccessTier;
  gating_reason: string;
  api_surface: ApiSurface;
  buildability_verdict: Verdict;
  blocker: string | null;
  evidence_urls: string[];
  rate_limit_notes: string;
  notable_signals: string;
  agent_confidence: number;
  needs_human_review: boolean;
  human_review_reason: string;
}

export interface Blocker {
  blocker: string;
  count: number;
  example_apps: string[];
}

export interface EasyWin {
  id: number;
  app: string;
  category: string;
  auth_methods: string[];
  api_surface_type: string;
  evidence_urls: string[];
}

export interface Outreach {
  id: number;
  app: string;
  category: string;
  access_tier: string;
  blocker: string | null;
  evidence_urls: string[];
}

export interface Patterns {
  total_apps: number;
  auth_method_distribution: {
    overall: Record<string, number>;
    by_category: Record<string, Record<string, number>>;
  };
  access_tier_distribution: {
    overall: Record<string, number>;
    by_category: Record<string, Record<string, number>>;
  };
  buildability_distribution: Record<string, number>;
  human_review_distribution: Record<string, number>;
  top_blockers: Blocker[];
  easy_wins: EasyWin[];
  needs_outreach: Outreach[];
  headline_findings: string[];
}

export interface FieldClass {
  structured_decision: number;
  advisory_free_text: number;
}

export interface FailureMode {
  mode: string;
  count: number;
  examples: string[];
}

export interface AccuracyReport {
  pass1_accuracy: number;
  pass2_accuracy: number;
  per_field_accuracy: { pass1: Record<string, number>; pass2: Record<string, number> };
  field_class_accuracy: { pass1: FieldClass; pass2: FieldClass };
  metric_notes: string;
  sample_size: number;
  sample_app_ids: number[];
  sample_apps: string[];
  skipped_app_ids: number[];
  methodology: Record<string, string>;
  common_failure_modes: FailureMode[];
  recommended_agent_fixes: string[];
}

export interface VerificationRow {
  pass: 'pass1' | 'pass2';
  app_id: number;
  app: string;
  category: string;
  field: string;
  agent_answer: unknown;
  verified_answer: unknown;
  correct: boolean;
  evidence_checked: string[];
}

export interface GoldRow {
  id: number;
  app: string;
  field: string;
  agent: unknown;
  gold: unknown;
  correct: boolean;
}

export interface GoldAccuracy {
  gold_size: number;
  methodology: string;
  objective_accuracy: { pass1: number; pass2: number };
  auth_methods_accuracy: { pass1: number; pass2: number };
  api_type_accuracy: { pass1: number; pass2: number };
  access_tier_accuracy: { pass1: number; pass2: number };
  pass1_rows: GoldRow[];
  pass2_rows: GoldRow[];
}

export interface AutomationReport {
  total_apps: number;
  traces_found: number;
  fully_automated_apps: number;
  needed_human_apps: number;
  fully_automated_pct: number;
  human_review_reason_breakdown: Record<string, number>;
  totals: {
    tool_calls: number;
    model_rounds: number;
    prompt_tokens: number;
    completion_tokens: number;
  };
  averages_per_app: { tool_calls: number; model_rounds: number };
  composio_tool_usage: Record<string, number>;
}

// One line of a per-app trace JSONL file (public/data/traces/{id}.jsonl).
export interface TraceEvent {
  ts: string;
  event: string;
  [key: string]: unknown;
}

export interface ResearchData {
  apps: AppRecord[];
  patterns: Patterns;
  accuracy: AccuracyReport;
  verification: VerificationRow[];
  gold: GoldAccuracy;
  automation: AutomationReport;
}
