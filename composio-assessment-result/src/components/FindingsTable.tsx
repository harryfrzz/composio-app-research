import { useMemo, useState } from 'react';
import type { AppRecord, AccessTier } from '../types/data';
import { AccessBadge, VerdictBadge } from './Badges';
import { ACCESS_LABELS, authLabel, host, isSelfServe } from '../lib/format';

interface Props {
  apps: AppRecord[];
}

type SortKey = 'app' | 'category' | 'access' | 'verdict';
type SortDir = 'asc' | 'desc';

const ACCESS_ORDER: AccessTier[] = [
  'self_serve_free',
  'self_serve_trial',
  'paid_plan_required',
  'admin_approval_required',
  'partner_gated_contact_sales',
];
const VERDICT_ORDER = ['ready_today', 'ready_with_workaround', 'blocked'];

function na(value: string): React.ReactNode {
  return value && value.trim() ? value : <span className="na">not captured</span>;
}

export default function FindingsTable({ apps }: Props) {
  const [category, setCategory] = useState('all');
  const [access, setAccess] = useState('all');
  const [sortKey, setSortKey] = useState<SortKey>('app');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [expanded, setExpanded] = useState<number | null>(null);
  const [collapsed, setCollapsed] = useState(true);

  const categories = useMemo(
    () => Array.from(new Set(apps.map((a) => a.category))).sort(),
    [apps],
  );

  const rows = useMemo(() => {
    let out = apps.filter((a) => {
      if (category !== 'all' && a.category !== category) return false;
      if (access === 'all') return true;
      if (access === 'self_serve') return isSelfServe(a.access_tier);
      if (access === 'gated') return !isSelfServe(a.access_tier);
      return a.access_tier === access;
    });
    const dir = sortDir === 'asc' ? 1 : -1;
    out = [...out].sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'app') cmp = a.app.localeCompare(b.app);
      else if (sortKey === 'category') cmp = a.category.localeCompare(b.category) || a.app.localeCompare(b.app);
      else if (sortKey === 'access')
        cmp = ACCESS_ORDER.indexOf(a.access_tier) - ACCESS_ORDER.indexOf(b.access_tier) || a.app.localeCompare(b.app);
      else if (sortKey === 'verdict')
        cmp =
          VERDICT_ORDER.indexOf(a.buildability_verdict) - VERDICT_ORDER.indexOf(b.buildability_verdict) ||
          a.app.localeCompare(b.app);
      return cmp * dir;
    });
    return out;
  }, [apps, category, access, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(key);
      setSortDir('asc');
    }
  }

  const caret = (key: SortKey) => (sortKey === key ? <span className="caret">{sortDir === 'asc' ? '↑' : '↓'}</span> : null);

  return (
    <section className="section" id="findings">
      <div className="wrap">
        <div className="section-head">
          <span className="section-num">05</span>
          <div>
            <div className="kicker">The findings</div>
            <div className="bp-figline">FIG_05 · APP LEDGER · N={apps.length}</div>
            <h2 className="bp-title">All 100 apps, one row each</h2>
            <p className="section-sub">
              Filter by category or access, sort any column, expand a row for the gating reason,
              API breadth, MCP status, and evidence.
            </p>
          </div>
        </div>

        <button
          className="table-collapse"
          onClick={() => setCollapsed((c) => !c)}
          aria-expanded={!collapsed}
        >
          <span className="tc-label">
            {collapsed ? 'Show' : 'Hide'} the full table of {apps.length} apps
          </span>
          <span className="tc-meta">
            click to {collapsed ? 'expand' : 'collapse'} {collapsed ? '▸' : '▾'}
          </span>
        </button>

        {!collapsed && (
          <>
        <div className="table-tools">
          <select className="control" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="all">All categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select className="control" value={access} onChange={(e) => setAccess(e.target.value)}>
            <option value="all">All access tiers</option>
            <option value="self_serve">— Self-serve (any) —</option>
            <option value="gated">— Gated (any) —</option>
            {ACCESS_ORDER.map((t) => (
              <option key={t} value={t}>
                {ACCESS_LABELS[t]}
              </option>
            ))}
          </select>
          <span className="count">
            {rows.length} of {apps.length} apps
          </span>
        </div>

        <div className="table-scroll">
          <table className="findings-table">
            <thead>
              <tr>
                <th className="sortable" onClick={() => toggleSort('app')} style={{ minWidth: 200 }}>
                  App {caret('app')}
                </th>
                <th>Auth</th>
                <th className="sortable" onClick={() => toggleSort('access')}>
                  Access {caret('access')}
                </th>
                <th>API</th>
                <th className="sortable" onClick={() => toggleSort('verdict')}>
                  Buildability {caret('verdict')}
                </th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => {
                const isOpen = expanded === a.id;
                return (
                  <ExpandableRow
                    key={a.id}
                    app={a}
                    isOpen={isOpen}
                    onToggle={() => setExpanded(isOpen ? null : a.id)}
                  />
                );
              })}
            </tbody>
          </table>
        </div>
          </>
        )}
      </div>
    </section>
  );
}

function ExpandableRow({ app, isOpen, onToggle }: { app: AppRecord; isOpen: boolean; onToggle: () => void }) {
  return (
    <>
      <tr className={isOpen ? 'expanded' : ''} onClick={onToggle} style={{ cursor: 'pointer' }}>
        <td>
          <span className="cell-app">{app.app}</span>
          <span className="cat">{app.category}</span>
        </td>
        <td>
          <span className="auth-cell">
            {app.auth_methods.length ? (
              app.auth_methods.map((m) => (
                <span className="tag" key={m}>
                  {authLabel(m)}
                </span>
              ))
            ) : (
              <span className="na">not captured</span>
            )}
          </span>
        </td>
        <td>
          <AccessBadge tier={app.access_tier} />
        </td>
        <td>
          <span className="tag">{app.api_surface.type}</span>
          {app.api_surface.mcp_exists && (
            <span className="tag" style={{ marginLeft: 4, color: 'var(--accent-ink)' }}>
              MCP
            </span>
          )}
        </td>
        <td>
          <VerdictBadge verdict={app.buildability_verdict} />
        </td>
        <td>
          {app.evidence_urls.length ? (
            <button className="expand-btn" onClick={(e) => { e.stopPropagation(); onToggle(); }}>
              {app.evidence_urls.length} source{app.evidence_urls.length > 1 ? 's' : ''} {isOpen ? '▾' : '▸'}
            </button>
          ) : (
            <span className="na">none</span>
          )}
        </td>
      </tr>
      {isOpen && (
        <tr className="expand-row">
          <td colSpan={6}>
            <div className="expand-panel">
              <div className="kv" style={{ gridColumn: '1 / -1' }}>
                <div className="k">Description</div>
                <div className="v">{na(app.description)}</div>
              </div>
              <div className="kv">
                <div className="k">
                  Access reason {app.needs_human_review && <span style={{ color: 'var(--warn)' }}>· flagged for review</span>}
                </div>
                <div className="v">
                  {app.access_tier === 'self_serve_free' && !app.gating_reason ? (
                    <span className="muted">Self-serve, free — no gate.</span>
                  ) : (
                    na(app.gating_reason)
                  )}
                </div>
              </div>
              <div className="kv">
                <div className="k">Blocker</div>
                <div className="v">{app.blocker ? app.blocker : <span className="muted">none</span>}</div>
              </div>
              <div className="kv">
                <div className="k">API breadth</div>
                <div className="v">{na(app.api_surface.breadth)}</div>
              </div>
              <div className="kv">
                <div className="k">MCP</div>
                <div className="v">
                  {app.api_surface.mcp_exists ? na(app.api_surface.mcp_notes || 'Exists') : <span className="muted">None found</span>}
                </div>
              </div>
              {app.notable_signals && (
                <div className="kv" style={{ gridColumn: '1 / -1' }}>
                  <div className="k">Notable signals</div>
                  <div className="v">{app.notable_signals}</div>
                </div>
              )}
              {app.needs_human_review && app.human_review_reason && (
                <div className="kv" style={{ gridColumn: '1 / -1' }}>
                  <div className="k">Human-review note</div>
                  <div className="v" style={{ color: 'var(--warn)' }}>{app.human_review_reason}</div>
                </div>
              )}
              <div className="kv" style={{ gridColumn: '1 / -1' }}>
                <div className="k">Evidence · confidence {app.agent_confidence}/100</div>
                <div className="v evlinks">
                  {app.evidence_urls.map((u) => (
                    <a key={u} href={u} target="_blank" rel="noreferrer noopener">
                      {host(u)} ↗
                    </a>
                  ))}
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
