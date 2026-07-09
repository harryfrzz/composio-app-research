import type { AccessTier, Verdict } from '../types/data';
import { ACCESS_LABELS, VERDICT_LABELS, isSelfServe } from '../lib/format';

// Access tier: self-serve reads as positive (ok), any gate reads as caution/bad.
// Two-state coloring, not a rainbow — the gating reason carries the detail.
export function AccessBadge({ tier }: { tier: AccessTier }) {
  const tone = isSelfServe(tier)
    ? 'ok'
    : tier === 'partner_gated_contact_sales'
      ? 'bad'
      : 'warn';
  return (
    <span className={`pill ${tone}`}>
      <span className="dot" />
      {ACCESS_LABELS[tier] ?? tier}
    </span>
  );
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const tone = verdict === 'ready_today' ? 'ok' : verdict === 'blocked' ? 'bad' : 'warn';
  return (
    <span className={`pill ${tone}`}>
      <span className="dot" />
      {VERDICT_LABELS[verdict] ?? verdict}
    </span>
  );
}
