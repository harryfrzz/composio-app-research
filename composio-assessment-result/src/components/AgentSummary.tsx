import type { AutomationReport, Patterns } from '../types/data';
import { titleize } from '../lib/format';

interface Props {
  patterns: Patterns;
  automation: AutomationReport;
}

// Human labels for the review-reason keys — the auto-titleized versions read badly
// ("Mcp Uncertainty", "Docs Unfetchable Or Js").
const REASON_LABELS: Record<string, string> = {
  gated_or_pricing_ambiguity: 'Gated / pricing ambiguity',
  auth_inference: 'Auth inference',
  mcp_uncertainty: 'MCP uncertainty',
  docs_unfetchable_or_js: 'Docs unfetchable / JS-rendered',
};

export default function AgentSummary({ patterns, automation }: Props) {
  const flagged = patterns.human_review_distribution.needs_review ?? 0;
  const verified = patterns.human_review_distribution.agent_verified ?? 0;
  const total = flagged + verified;
  const toolCalls = automation.totals.tool_calls;

  const reasons = Object.entries(automation.human_review_reason_breakdown).sort((a, b) => b[1] - a[1]);
  const tools = Object.entries(automation.composio_tool_usage).sort((a, b) => b[1] - a[1]);

  return (
    <section className="section agent-summary" id="agent">
      <div className="wrap">
        <div className="section-head">
          <span className="section-num">01</span>
          <div>
            <div className="kicker">The agent</div>
            <div className="bp-figline">FIG_01 · AUTOMATION · {toolCalls.toLocaleString()} TOOL CALLS</div>
            <h2 className="bp-title">What was built, and where it needed a human</h2>
          </div>
        </div>

        <div className="agent-copy">
          <p className="agent-lede">
            A reasoning LLM plans each app; <strong>Composio's SDK + hosted MCP</strong> is the tool
            layer it calls to read the web — search + a headless browser toolkit. Dogfooding the
            exact infrastructure this research feeds.
          </p>
          <ul className="prose-list">
            <li>
              <strong>Structured output</strong> — strict function-call / Pydantic object;
              malformed output is rejected and retried, never regex-parsed.
            </li>
            <li>
              <strong>Concurrent + checkpointed</strong> — parallel batches with retry/backoff;
              each row is written the moment it finishes, so a crash never loses progress.
            </li>
            <li>
              <strong>Fully traced</strong> — every tool call logged per app (see the proof below).
            </li>
          </ul>
          <p className="agent-runline">
            Across {total} apps it made <strong>{toolCalls.toLocaleString()}</strong> Composio tool
            calls — <strong>{automation.averages_per_app.tool_calls}</strong> per app.{' '}
            <strong>{verified}</strong> of {total} rows came back fully agent-verified;{' '}
            <strong>{flagged}</strong> were flagged for a human, broken down below.
          </p>
        </div>

        <div className="agent-flagged">
          <h3 className="flagged-title">Why {flagged} flagged for a human</h3>

          <div className="bp-list">
            <div className="bp-list-head">
              <span>Flag reason</span>
              <span className="bp-hd-cov">Share of flagged</span>
              <span className="bp-hd-count">Apps</span>
              <span className="bp-hd-code" />
            </div>

            {reasons.map(([reason, n], i) => (
              <div className="bp-tier" key={reason}>
                <div className="bp-row bp-row-static">
                  <span className="bp-idx">{i}.</span>
                  <span className="bp-bullet" aria-hidden="true" />
                  <span className="bp-titlecell">
                    <span className="bp-rowtitle">{REASON_LABELS[reason] ?? titleize(reason)}</span>
                    <span className="bp-scope">{Math.round((n / flagged) * 100)}% of flagged</span>
                  </span>
                  <span className="bp-bar" aria-hidden="true">
                    <span
                      className="bp-bar-fill"
                      style={{ width: `${Math.max((n / flagged) * 100, 2)}%` }}
                    />
                  </span>
                  <span className="bp-count">
                    <b>{n}</b> / {flagged}
                  </span>
                  <span className="bp-code">{String(i).padStart(2, '0')}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="foot-label agent-tools-title">Composio tools used</div>
          <div className="evlinks">
            {tools.map(([name, n]) => (
              <span className="tag" key={name}>
                {name.replace(/^COMPOSIO_/, '')} · {n}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
