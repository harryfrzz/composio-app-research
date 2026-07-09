import type { AppRecord, GoldAccuracy, Patterns } from '../types/data';
import { pct } from '../lib/format';

interface Props {
  patterns: Patterns;
  gold: GoldAccuracy;
  apps: AppRecord[];
}

export default function Headline({ patterns, gold, apps }: Props) {
  const categories = new Set(apps.map((a) => a.category)).size;
  const readyToday = patterns.buildability_distribution.ready_today ?? 0;
  const easyWins = patterns.easy_wins.length;

  return (
    <header className="hero wrap" id="top">
      <div className="hero-eyebrow">Composio · AI Product Ops — App Research</div>
      <h1>Which of 100 apps can become an agent toolkit today — and what blocks the rest.</h1>
      <p className="hero-lede">
        An agent built on Composio's own SDK + hosted MCP researched 100 apps — auth, access tier,
        API surface, and a buildability verdict, with an evidence URL for every answer.
      </p>

      <div className="statstrip" role="list">
        <div className="stat" role="listitem">
          <div className="num">{patterns.total_apps}</div>
          <div className="lbl">apps · {categories} categories</div>
        </div>
        <div className="stat" role="listitem">
          <div className="num">{readyToday}</div>
          <div className="lbl">ready to build today</div>
        </div>
        <div className="stat" role="listitem">
          <div className="num">{easyWins}</div>
          <div className="lbl">easy wins</div>
        </div>
        <div className="stat" role="listitem">
          <div className="num">
            {pct(gold.objective_accuracy.pass1)}
            <span className="arrow">→</span>
            <span className="to">{pct(gold.objective_accuracy.pass2)}</span>
          </div>
          <div className="lbl">verified accuracy (after correction)</div>
        </div>
      </div>

      <div className="findings">
        {patterns.headline_findings.map((finding, i) => (
          <div className="finding" key={i}>
            <span className="idx">{String(i + 1).padStart(2, '0')}</span>
            <p>{finding}</p>
          </div>
        ))}
      </div>
    </header>
  );
}
