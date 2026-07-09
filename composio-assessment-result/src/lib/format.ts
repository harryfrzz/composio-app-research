import type { AccessTier, Verdict } from '../types/data';

export const ACCESS_LABELS: Record<AccessTier, string> = {
  self_serve_free: 'Self-serve · free',
  self_serve_trial: 'Self-serve · trial',
  paid_plan_required: 'Paid plan required',
  admin_approval_required: 'Admin approval',
  partner_gated_contact_sales: 'Partner / contact sales',
};

// Two-state read for the "self-serve vs gated" story the brief asks for.
export function isSelfServe(tier: AccessTier): boolean {
  return tier === 'self_serve_free' || tier === 'self_serve_trial';
}

export const VERDICT_LABELS: Record<Verdict, string> = {
  ready_today: 'Ready today',
  ready_with_workaround: 'With workaround',
  blocked: 'Blocked',
};

export const AUTH_LABELS: Record<string, string> = {
  oauth2: 'OAuth2',
  api_key: 'API key',
  basic: 'Basic',
  token: 'Token',
  other: 'Other',
};

export function authLabel(method: string): string {
  return AUTH_LABELS[method] ?? method;
}

export function titleize(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function pct1(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

// Compact host for evidence links.
export function host(url: string): string {
  try {
    return new URL(url).host.replace(/^www\./, '');
  } catch {
    return url;
  }
}
