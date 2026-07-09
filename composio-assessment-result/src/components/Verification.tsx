import { useMemo, useState } from 'react';
import type {
  AccuracyReport,
  EvidenceLiveness,
  GoldAccuracy,
  GoldRow,
  GoldStandard,
  VerificationRow,
} from '../types/data';
import { host, pct, pct1 } from '../lib/format';

interface Props {
  accuracy: AccuracyReport;
  verification: VerificationRow[];
  gold: GoldAccuracy;
  goldStandard: GoldStandard;
  evidence: EvidenceLiveness;
}

function fmt(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—';
  if (Array.isArray(v)) return v.length ? v.join(', ') : '—';
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

// Per-app objective correctness (auth_methods + api_surface.type) for one pass,
// read straight off the gold rows so nothing is hardcoded.
type ObjResult = { auth: boolean | null; api: boolean | null };

function objectiveByApp(rows: GoldRow[]): Map<string, ObjResult> {
  const m = new Map<string, ObjResult>();
  for (const r of rows) {
    if (r.field !== 'auth_methods' && r.field !== 'api_surface_type') continue;
    const e = m.get(r.app) ?? { auth: null, api: null };
    if (r.field === 'auth_methods') e.auth = r.correct;
    else e.api = r.correct;
    m.set(r.app, e);
  }
  return m;
}

function mark(v: boolean | null | undefined) {
  if (v === null || v === undefined) return <span className="ga-na">—</span>;
  return v ? <span className="ok">✓</span> : <span className="no">✕</span>;
}

function ObjMarks({ r }: { r?: ObjResult }) {
  return (
    <span className="ga-marks">
      <span className="ga-mk">auth {mark(r?.auth)}</span>
      <span className="ga-mk">API {mark(r?.api)}</span>
    </span>
  );
}

export default function Verification({
  accuracy,
  verification,
  gold,
  goldStandard,
  evidence,
}: Props) {
  const [pass, setPass] = useState<'pass1' | 'pass2'>('pass2');
  const [missesOnly, setMissesOnly] = useState(true);
  const [collapsed, setCollapsed] = useState(true);

  const goldDelta = gold.objective_accuracy.pass2 - gold.objective_accuracy.pass1;
  const llmDelta = accuracy.pass2_accuracy - accuracy.pass1_accuracy;

  const obj1 = useMemo(() => objectiveByApp(gold.pass1_rows), [gold]);
  const obj2 = useMemo(() => objectiveByApp(gold.pass2_rows), [gold]);
  const urlsChecked = evidence.unique_urls_checked;
  const liveUrls = evidence.url_verdict_counts.ok;
  const zeroLive = evidence.rows_with_zero_live_evidence.length;

  const rows = useMemo(() => {
    return verification.filter((r) => r.pass === pass && (!missesOnly || !r.correct));
  }, [verification, pass, missesOnly]);

  const passRows = verification.filter((r) => r.pass === pass);
  const correctCount = passRows.filter((r) => r.correct).length;

  return (
    <section className="section" id="verification">
      <div className="wrap">
        <div className="section-head">
          <span className="section-num">04</span>
          <div>
            <div className="kicker">The verification</div>
            <div className="bp-figline">
              FIG_04 · ACCURACY · {pct(gold.objective_accuracy.pass1)} → {pct(gold.objective_accuracy.pass2)}
            </div>
            <h2 className="bp-title">Accuracy, checked two ways — and shown honestly</h2>
            <p className="section-sub">
              The corrected Pass-2 prompt ran across all 100 apps. Accuracy was then checked
              independently: 8 apps were hand-audited against official docs (the number to trust),
              and an LLM verifier covered a hard 20-app sample spanning all 10 categories as a
              secondary diagnostic.
            </p>
          </div>
        </div>

        <div className="beforeafter">
          <div className="ba-card card authoritative">
            <div className="ba-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Hand-verified vs official docs</span>
              <span className="ba-badge">authoritative</span>
            </div>
            <div className="ba-nums">
              <span className="from">{pct(gold.objective_accuracy.pass1)}</span>
              <span className="arrow">→</span>
              <span className="to">{pct(gold.objective_accuracy.pass2)}</span>
            </div>
            <div className="delta" style={{ color: 'var(--ok)' }}>
              +{Math.round(goldDelta * 100)} pts · objective fields (auth + API type), n={gold.gold_size}
            </div>
            <div className="ba-note">
              Fields read by hand from official docs, source URL per app. auth_methods alone doubled
              ({pct(gold.auth_methods_accuracy.pass1)} → {pct(gold.auth_methods_accuracy.pass2)}).
              The number to trust.
            </div>
          </div>

          <div className="ba-card card">
            <div className="ba-label">Automated LLM verifier · 20 apps</div>
            <div className="ba-nums">
              <span className="from">{pct1(accuracy.pass1_accuracy)}</span>
              <span className="arrow">→</span>
              <span className="to" style={{ fontSize: 34, color: 'var(--ink-2)' }}>{pct1(accuracy.pass2_accuracy)}</span>
            </div>
            <div className="delta muted">
              {llmDelta >= 0 ? '+' : ''}{(llmDelta * 100).toFixed(1)} pts overall · structured fields{' '}
              {pct(accuracy.field_class_accuracy.pass1.structured_decision)} →{' '}
              {pct(accuracy.field_class_accuracy.pass2.structured_decision)}
            </div>
            <div className="ba-note">
              An independent LLM re-derives every field from fresh docs. Honest, not dressed up: it
              scores prose by token-overlap and is itself noisy (it once called Salesforce auth{' '}
              <span className="mono">other</span>, which is wrong) — so LLM-vs-LLM agreement caps low.
            </div>
          </div>
        </div>

        <div className="gold-audit">
          <div className="ga-head">
            <h3 className="ga-title">The 8-app human audit — read by hand from official docs</h3>
            <p className="ga-sub">
              The <b>75%</b> is objective-field accuracy (auth&nbsp;+&nbsp;API type) on this{' '}
              <b>8-app sample</b> — not a 100-app measurement. All 100 apps received the corrected
              Pass-2 prompt; these 8 are the hand-checked ground truth it is spot-checked against.
            </p>
          </div>
          <div className="ga-scroll">
            <table className="ga-table">
              <thead>
                <tr>
                  <th>App</th>
                  <th>Pass&nbsp;1 · obj</th>
                  <th>Pass&nbsp;2 · obj</th>
                  <th>Official source</th>
                  <th>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {goldStandard.apps.map((a) => (
                  <tr key={a.id}>
                    <td className="ga-app">{a.app}</td>
                    <td>
                      <ObjMarks r={obj1.get(a.app)} />
                    </td>
                    <td>
                      <ObjMarks r={obj2.get(a.app)} />
                    </td>
                    <td className="ga-src">
                      <a href={a.source} target="_blank" rel="noreferrer noopener" title={a.source}>
                        {host(a.source)}
                      </a>
                    </td>
                    <td className="ga-ev">
                      <details>
                        <summary>quote</summary>
                        <span className="ga-quote">“{a.quote}”</span>
                      </details>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="ev-trust" aria-label="Evidence-URL liveness">
            <span className="ev-trust-lbl">Evidence liveness</span>
            <span className="ev-stat">
              <b>{urlsChecked}</b> URLs checked
            </span>
            <span className="ev-stat">
              <b>{liveUrls}</b> live
            </span>
            <span className="ev-stat">
              <b>{zeroLive}</b> rows with zero live evidence
            </span>
          </div>
        </div>

        <button
          className="table-collapse"
          onClick={() => setCollapsed((c) => !c)}
          aria-expanded={!collapsed}
        >
          <span className="tc-label">
            {collapsed ? 'Show' : 'Hide'} the LLM verifier’s field-by-field comparison
          </span>
          <span className="tc-meta">
            click to {collapsed ? 'expand' : 'collapse'} {collapsed ? '▸' : '▾'}
          </span>
        </button>

        {!collapsed && (
          <>
        <div className="hm-tools">
          <div className="seg">
            <button className={pass === 'pass1' ? 'active' : ''} onClick={() => setPass('pass1')}>
              Pass 1
            </button>
            <button className={pass === 'pass2' ? 'active' : ''} onClick={() => setPass('pass2')}>
              Pass 2 (corrected)
            </button>
          </div>
          <div className="seg">
            <button className={missesOnly ? 'active' : ''} onClick={() => setMissesOnly(true)}>
              Misses only
            </button>
            <button className={!missesOnly ? 'active' : ''} onClick={() => setMissesOnly(false)}>
              All fields
            </button>
          </div>
          <span className="count mono" style={{ marginLeft: 'auto', color: 'var(--muted)', fontSize: 12 }}>
            {pass} · {correctCount}/{passRows.length} fields agree · showing {rows.length}
          </span>
        </div>

        <div className="hitmiss-scroll">
          <table className="hitmiss">
            <thead>
              <tr>
                <th className="mark" />
                <th style={{ minWidth: 120 }}>App</th>
                <th>Field</th>
                <th>Agent answer</th>
                <th>Independently verified</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td className="mark">{r.correct ? <span className="ok">✓</span> : <span className="no">✕</span>}</td>
                  <td style={{ fontWeight: 600, whiteSpace: 'nowrap' }}>{r.app}</td>
                  <td className="field-cell">{r.field}</td>
                  <td className={`ans ${r.correct ? '' : 'miss-agent'}`}>{fmt(r.agent_answer)}</td>
                  <td className="ans">{fmt(r.verified_answer)}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', color: 'var(--muted)', padding: 24 }}>
                    No rows for this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
          </>
        )}
      </div>
    </section>
  );
}
