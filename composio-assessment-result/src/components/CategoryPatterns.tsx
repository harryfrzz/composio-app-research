import type { Patterns } from '../types/data';
import { ACCESS_LABELS, authLabel } from '../lib/format';
import type { AccessTier } from '../types/data';

interface Props {
  patterns: Patterns;
}

// Self-serve = free + trial. Gated = paid plan / admin approval / partner-contact-sales.
const SELF_SERVE_KEYS = ['self_serve_free', 'self_serve_trial'] as const;
const GATED_KEYS = [
  'paid_plan_required',
  'admin_approval_required',
  'partner_gated_contact_sales',
] as const;

function sum(dist: Record<string, number>, keys: readonly string[]): number {
  return keys.reduce((n, k) => n + (dist[k] ?? 0), 0);
}

// The category-level self-serve/gated matrix plus a handful of named easy-wins
// and needs-outreach examples — the two-minute read of the whole 100-app set,
// visible without opening the full ledger below.
export default function CategoryPatterns({ patterns }: Props) {
  const byCategory = patterns.access_tier_distribution.by_category;

  const rows = Object.entries(byCategory)
    .map(([category, dist]) => {
      const selfServe = sum(dist, SELF_SERVE_KEYS);
      const gated = sum(dist, GATED_KEYS);
      return { category, selfServe, gated, total: selfServe + gated };
    })
    // Lead with the categories that are easiest to build against.
    .sort((a, b) => b.selfServe - a.selfServe || b.total - a.total);

  const maxTotal = Math.max(...rows.map((r) => r.total), 1);

  const easyWins = patterns.easy_wins.slice(0, 6);
  const outreach = patterns.needs_outreach.slice(0, 6);

  return (
    <section className="section catpatterns" id="patterns">
      <div className="wrap">
        <div className="section-head">
          <span className="section-num">01</span>
          <div>
            <div className="kicker">The patterns</div>
            <div className="bp-figline">FIG_01 · ACCESS TIER · {rows.length} CATEGORIES</div>
            <h2 className="bp-title">Self-serve vs gated, by category</h2>
            <p className="section-sub">
              Where a builder can sign up and get an API key today (self-serve: free or trial)
              versus where a paid plan, admin approval, or a sales conversation stands in the way
              (gated). The full 100-app ledger is in section 05.
            </p>
          </div>
        </div>

        <div className="catmatrix" role="table" aria-label="Access tier by category">
          <div className="cm-head" role="row">
            <span role="columnheader">Category</span>
            <span className="cm-bar-head" role="columnheader">
              <span className="cm-key">
                <span className="cm-dot self" aria-hidden="true" /> self-serve
              </span>
              <span className="cm-key">
                <span className="cm-dot gated" aria-hidden="true" /> gated
              </span>
            </span>
            <span className="cm-num-head" role="columnheader">
              self / gated
            </span>
          </div>
          {rows.map((r) => (
            <div className="cm-row" role="row" key={r.category}>
              <span className="cm-cat" role="cell">
                {r.category}
              </span>
              <span className="cm-bar" role="cell" aria-hidden="true">
                <span
                  className="cm-seg self"
                  style={{ width: `${(r.selfServe / maxTotal) * 100}%` }}
                />
                <span
                  className="cm-seg gated"
                  style={{ width: `${(r.gated / maxTotal) * 100}%` }}
                />
              </span>
              <span className="cm-nums" role="cell">
                <b className="cm-self">{r.selfServe}</b>
                <span className="cm-slash">/</span>
                <b className="cm-gated">{r.gated}</b>
              </span>
            </div>
          ))}
        </div>

        <div className="patexamples">
          <div className="patcol">
            <div className="patcol-head">
              <span className="cm-dot self" aria-hidden="true" /> Easy wins — build today
            </div>
            <ul className="patlist">
              {easyWins.map((w) => (
                <li key={w.id}>
                  <span className="pat-app">{w.app}</span>
                  <span className="pat-meta">{w.category}</span>
                  <span className="pat-tags">
                    {w.auth_methods.map((m) => authLabel(m)).join(' · ')} · {w.api_surface_type}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="patcol">
            <div className="patcol-head">
              <span className="cm-dot gated" aria-hidden="true" /> Needs outreach — gated
            </div>
            <ul className="patlist">
              {outreach.map((o) => (
                <li key={o.id}>
                  <span className="pat-app">{o.app}</span>
                  <span className="pat-meta">{o.category}</span>
                  <span className="pat-tags">
                    {ACCESS_LABELS[o.access_tier as AccessTier] ?? o.access_tier}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
