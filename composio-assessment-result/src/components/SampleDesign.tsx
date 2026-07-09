import { useMemo, useState } from 'react';
import type { AccuracyReport, AppRecord, GoldAccuracy, Patterns } from '../types/data';

interface Props {
  apps: AppRecord[];
  accuracy: AccuracyReport;
  gold: GoldAccuracy;
  patterns: Patterns;
}

// The three-tier sampling design, laid out as a technical-manual index:
// mono labels, index numerals, square bullets, coverage bars, right-aligned
// counts. Same warm-paper + indigo palette as the rest of the page — only the
// blueprint *layout* is borrowed. Explains WHY each tier's N is what it is:
// correction is automated (all 100), LLM verification is oracle-cost-bound (20),
// gold is human-labor-bound (8).
export default function SampleDesign({ apps, accuracy, gold, patterns }: Props) {
  // All tiers start collapsed; the reader taps the one they want.
  const [open, setOpen] = useState<'correction' | 'llm' | 'gold' | null>(null);

  const total = patterns.total_apps;
  const sampleSize = accuracy.sample_size;
  const goldSize = gold.gold_size;

  // The 20-app sample is built as 10 forced-hard apps + 10 one-per-category.
  const sampleApps = accuracy.sample_apps;
  const hardApps = sampleApps.slice(0, 10);
  const categoryReps = sampleApps.slice(10);

  // name → category, so each category representative can show what it stands in for.
  const catByName = useMemo(() => {
    const m = new Map<string, string>();
    for (const a of apps) m.set(a.app.toLowerCase(), a.category);
    return m;
  }, [apps]);
  const categoryCount = useMemo(() => new Set(apps.map((a) => a.category)).size, [apps]);

  // 8 unique gold apps, read by hand from official docs.
  const goldApps = useMemo(() => {
    const seen: string[] = [];
    for (const r of gold.pass2_rows) if (!seen.includes(r.app)) seen.push(r.app);
    return seen;
  }, [gold]);

  const tiers = [
    {
      key: 'correction' as const,
      index: '0',
      code: '00',
      title: 'Correction',
      scope: 'Agent · every app',
      note: 'ran on all',
      covered: total,
    },
    {
      key: 'llm' as const,
      index: 'I',
      code: '01',
      title: 'LLM Verification',
      scope: '10 hard + 10 categories',
      note: 'independent oracle',
      covered: sampleSize,
    },
    {
      key: 'gold' as const,
      index: 'II',
      code: '02',
      title: 'Gold — hand-read',
      scope: 'Human vs official docs',
      note: 'read by hand',
      covered: goldSize,
    },
  ];

  return (
    <section className="section blueprint" id="design">
      <span className="bp-corner tl" aria-hidden="true" />
      <span className="bp-corner tr" aria-hidden="true" />
      <span className="bp-corner bl" aria-hidden="true" />
      <span className="bp-corner br" aria-hidden="true" />
      <div className="wrap">
        <div className="section-head">
          <span className="section-num">02</span>
          <div>
            <div className="kicker">The design</div>
            <div className="bp-figline">
              FIG_02 · SAMPLE DESIGN · N={total} → {sampleSize} → {goldSize}
            </div>
            <h2 className="bp-title">Why 100, then 20, then 8</h2>
            <p className="section-sub">
              Not a shortfall — a widening funnel. Each tier is bounded by a different cost:
              correction is automated, LLM verification pays an oracle per app, gold is read by a
              human. Tap a tier to see why its number is what it is.
            </p>
          </div>
        </div>

        <div className="bp-list">
          <div className="bp-list-head">
            <span>Tier</span>
            <span className="bp-hd-cov">Coverage</span>
            <span className="bp-hd-count">Apps</span>
            <span className="bp-hd-code" />
          </div>

          {tiers.map((t) => {
            const isOpen = open === t.key;
            const frac = t.covered / total;
            return (
              <div className={`bp-tier ${isOpen ? 'open' : ''}`} key={t.key}>
                <button
                  className="bp-row"
                  onClick={() => setOpen(isOpen ? null : t.key)}
                  aria-expanded={isOpen}
                >
                  <span className="bp-idx">{t.index}.</span>
                  <span className="bp-bullet" aria-hidden="true" />
                  <span className="bp-titlecell">
                    <span className="bp-rowtitle">{t.title}</span>
                    <span className="bp-scope">{t.scope}</span>
                  </span>
                  <span className="bp-bar" aria-hidden="true">
                    <span className="bp-bar-fill" style={{ width: `${Math.max(frac * 100, 6)}%` }} />
                  </span>
                  <span className="bp-count">
                    <b>{t.covered}</b> / {total}
                  </span>
                  <span className="bp-code">{t.code}</span>
                </button>

                {isOpen && t.key === 'correction' && (
                  <div className="bp-detail">
                    <p className="bp-prose">
                      Correction is automated — one prompt, one
                      pass. Cheap enough to run on the entire set, so it does: every one of the{' '}
                      {total} apps gets the failure-mode-corrected prompt, <b>0 failures</b>. Nothing
                      is sampled away at this stage — the funnel only narrows where cost forces it to.
                    </p>
                    <div className="bp-facts">
                      <div className="bp-fact">
                        <span className="bp-fact-num">{total}/{total}</span>
                        <span className="bp-fact-lbl">rows written</span>
                      </div>
                      <div className="bp-fact">
                        <span className="bp-fact-num">2</span>
                        <span className="bp-fact-lbl">passes · pass 1 + pass 2</span>
                      </div>
                      <div className="bp-fact">
                        <span className="bp-fact-num">0</span>
                        <span className="bp-fact-lbl">failures</span>
                      </div>
                    </div>
                  </div>
                )}

                {isOpen && t.key === 'llm' && (
                  <div className="bp-detail">
                    <p className="bp-prose">
                      Verification is not free. Each app here costs
                      a live documentation fetch <i>plus</i> a source-grounded LLM that re-derives
                      every field from scratch — roughly 5× the oracle spend of correction, per app.
                      Verifying all {total} would multiply that cost for sharply diminishing signal,
                      because the sample is engineered to already cover what matters.
                    </p>

                    <div className="bp-formula">
                      <span className="bp-term">
                        <b>10</b> hard, by name
                      </span>
                      <span className="bp-op">+</span>
                      <span className="bp-term">
                        <b>10</b> one per category
                      </span>
                      <span className="bp-op">=</span>
                      <span className="bp-term result">
                        <b>{sampleSize}</b> verified
                      </span>
                    </div>

                    <div className="bp-chipgroup">
                      <div className="bp-chip-label">
                        Forced in — the known-hard, partner-gated &amp; thin-doc cases
                      </div>
                      <div className="bp-chips">
                        {hardApps.map((a) => (
                          <span className="bp-chip hard" key={a}>
                            {a}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="bp-chipgroup">
                      <div className="bp-chip-label">
                        One representative per category — all {categoryCount} covered
                      </div>
                      <div className="bp-chips">
                        {categoryReps.map((a) => (
                          <span className="bp-chip" key={a}>
                            {a}
                            <em>{catByName.get(a.toLowerCase()) ?? '—'}</em>
                          </span>
                        ))}
                      </div>
                    </div>

                    <p className="bp-prose tail">
                      So the {sampleSize} is a design choice, not a limit hit by accident: every
                      category is represented and the failure-prone tail is verified, at a fifth of
                      the full-run oracle cost.
                    </p>
                  </div>
                )}

                {isOpen && t.key === 'gold' && (
                  <div className="bp-detail">
                    <p className="bp-prose">
                      Gold is the trust ceiling — bound by human
                      labor, not compute. Every field (auth + API type) is read by hand from official
                      docs, with a source URL and a quote per app. That hand-work caps the count:{' '}
                      <b>{goldSize}</b> well-documented, spot-checkable apps. Small on purpose —
                      high-integrity, not large-N. LLM-vs-LLM agreement tops out near 60% for
                      structural reasons; this human gold is the number to trust.
                    </p>
                    <div className="bp-chipgroup">
                      <div className="bp-chip-label">Read by hand from official docs</div>
                      <div className="bp-chips">
                        {goldApps.map((a) => (
                          <span className="bp-chip gold" key={a}>
                            {a}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <p className="bp-closing">
          <span className="bp-closing-mark" aria-hidden="true" />
          Widening funnel: automate on <b>{total}</b>, machine-verify on <b>{sampleSize}</b>,
          human-verify on <b>{goldSize}</b> — three tiers, three cost limits, deliberately nested.
        </p>
      </div>
    </section>
  );
}
