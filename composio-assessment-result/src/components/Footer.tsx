import { README_URL, REPO_URL } from '../lib/config';

const base = import.meta.env.BASE_URL;

const RAW_FILES = [
  ['pass2_corrected.json', '100 app records'],
  ['patterns.json', 'clusters'],
  ['accuracy_report.json', 'accuracy'],
  ['verification_sample.json', 'hits & misses'],
  ['gold_accuracy.json', 'hand-verified'],
];

export default function Footer() {
  return (
    <footer className="footer">
      <div className="wrap cols">
        <div>
          <div className="foot-label">Source</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <a href={REPO_URL} className="mono" style={{ fontSize: 13 }}>
              → research agent repository
            </a>
            <a href={README_URL} className="mono" style={{ fontSize: 13 }}>
              → README (setup, run, honest findings)
            </a>
            <a
              href={`${base}data/traces/001.jsonl`}
              target="_blank"
              rel="noreferrer noopener"
              className="mono"
              style={{ fontSize: 13 }}
              title="Unedited per-app tool-call trace — one log file per app (001–100)"
            >
              → data/traces/&lt;id&gt;.jsonl — per-app tool-call log
            </a>
          </div>
        </div>
        <div>
          <div className="foot-label">Raw data — directly fetchable, zero JS</div>
          <div className="rawdata">
            {RAW_FILES.map(([file, note], i) => (
              <span key={file}>
                <a href={`${base}data/${file}`} target="_blank" rel="noreferrer noopener" title={note}>
                  {file}
                </a>
                {i < RAW_FILES.length - 1 ? <span className="faint"> · </span> : null}
              </span>
            ))}
          </div>
          <p className="faint mono" style={{ fontSize: 11, marginTop: 10, maxWidth: '46ch' }}>
            An agent can consume the full dataset without running any JavaScript by fetching these
            static endpoints.
          </p>
        </div>
      </div>
    </footer>
  );
}
