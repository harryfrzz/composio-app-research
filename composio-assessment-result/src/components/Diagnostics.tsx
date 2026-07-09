import type { AccuracyReport } from '../types/data';
import { titleize } from '../lib/format';

interface Props {
  accuracy: AccuracyReport;
}

// Pass-1 failure taxonomy, rendered in the same blueprint row language as the
// design + agent sections (index · bullet · title · bar · count · code). Tinted
// with the --bad accent because every row here is a miss the corrected prompt fixed.
export default function Diagnostics({ accuracy }: Props) {
  const modes = [...accuracy.common_failure_modes].sort((a, b) => b.count - a.count);
  const totalMisses = modes.reduce((sum, m) => sum + m.count, 0);

  return (
    <section className="section blueprint diagnostics" id="diagnostics">
      <span className="bp-corner tl" aria-hidden="true" />
      <span className="bp-corner tr" aria-hidden="true" />
      <span className="bp-corner bl" aria-hidden="true" />
      <span className="bp-corner br" aria-hidden="true" />
      <div className="wrap">
        <div className="section-head">
          <span className="section-num">05</span>
          <div>
            <div className="kicker kicker-bad">Pass 1 diagnostics</div>
            <div className="bp-figline">FIG_05 · FAILURE MODES · {totalMisses} misses</div>
            <h2 className="bp-title">Why the misses happened</h2>
            <p className="section-sub">
              Diagnosed failure modes across the pass-1 sample. The corrected prompt targeted these
              directly.
            </p>
          </div>
        </div>

        <div className="bp-list diag-list">
          <div className="bp-list-head">
            <span>Failure mode</span>
            <span className="bp-hd-cov">Share of misses</span>
            <span className="bp-hd-count">Fields</span>
            <span className="bp-hd-code" />
          </div>

          {modes.map((m, i) => (
            <div className="bp-tier" key={m.mode}>
              <div className="bp-row bp-row-static">
                <span className="bp-idx">{i}.</span>
                <span className="bp-bullet" aria-hidden="true" />
                <span className="bp-titlecell">
                  <span className="bp-rowtitle">{titleize(m.mode)}</span>
                  <span className="bp-scope">{m.examples.slice(0, 3).join(' · ')}</span>
                </span>
                <span className="bp-bar" aria-hidden="true">
                  <span
                    className="bp-bar-fill"
                    style={{ width: `${Math.max((m.count / totalMisses) * 100, 2)}%` }}
                  />
                </span>
                <span className="bp-count">
                  <b>{m.count}</b> / {totalMisses}
                </span>
                <span className="bp-code">{String(i).padStart(2, '0')}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
