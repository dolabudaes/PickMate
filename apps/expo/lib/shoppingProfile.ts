import type { InferredPreference, ShoppingDecisionProfile, UserIntent } from '../types';

export type PreferenceLevel = 'high' | 'important' | 'flexible' | 'unspecified';

export type RankingPreferenceKey =
  | 'comfort'
  | 'noise_cancellation'
  | 'battery'
  | 'price_value'
  | 'quality'
  | 'durability';

export const RANKING_PREFERENCES: Array<{ key: RankingPreferenceKey; label: string; affectsRanking: true }> = [
  { key: 'comfort', label: 'Comfort', affectsRanking: true },
  { key: 'noise_cancellation', label: 'Noise Cancellation', affectsRanking: true },
  { key: 'battery', label: 'Battery Life', affectsRanking: true },
  { key: 'price_value', label: 'Value for Money', affectsRanking: true },
  { key: 'quality', label: 'Sound / Build Quality', affectsRanking: true },
  { key: 'durability', label: 'Risk Sensitivity', affectsRanking: true },
];

const INFERRED_TO_RANKING: Record<string, RankingPreferenceKey | null> = {
  comfort_attention: 'comfort',
  price_attention: 'price_value',
  risk_attention: 'durability',
  comparison_style: null,
  decision_confidence: null,
};

const CAMEL_TO_SNAKE: Record<string, string> = {
  comfort: 'comfort',
  noiseCancellation: 'noise_cancellation',
  battery: 'battery',
  priceValue: 'price_value',
  quality: 'quality',
  durability: 'durability',
  reviewConfidence: 'review_confidence',
  callQuality: 'call_quality',
};

export function preferenceLevel(weight?: number | null): PreferenceLevel {
  if (weight == null || Number.isNaN(weight)) return 'unspecified';
  if (weight >= 0.85) return 'high';
  if (weight >= 0.6) return 'important';
  if (weight >= 0.3) return 'flexible';
  return 'unspecified';
}

export function levelLabel(level: PreferenceLevel) {
  if (level === 'high') return 'High Priority';
  if (level === 'important') return 'Important';
  if (level === 'flexible') return 'Flexible';
  return 'Not Specified';
}

export function levelWeight(level: Exclude<PreferenceLevel, 'unspecified'>) {
  if (level === 'high') return 0.92;
  if (level === 'important') return 0.72;
  return 0.4;
}

export function rankingKeyFromClient(key: string) {
  return CAMEL_TO_SNAKE[key] ?? key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
}

export function clientKeyFromRanking(key: string) {
  return key.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());
}

export function rankingWeightFor(profile: ShoppingDecisionProfile, key: RankingPreferenceKey) {
  const camel = clientKeyFromRanking(key);
  const weight = profile.longTerm.stablePriorities[camel] ?? profile.longTerm.stablePriorities[key];
  return typeof weight === 'number' ? weight : null;
}

export function currentPurchaseSummary(intent: UserIntent) {
  const items: Array<{ label: string; value: string }> = [];
  if (intent.budget.max != null) items.push({ label: 'Budget', value: `Up to $${intent.budget.max}` });
  if (intent.useCases[0]) items.push({ label: 'Use case', value: humanizeKey(intent.useCases[0]) });
  const top = Object.entries(intent.softPreferences)
    .sort(([, a], [, b]) => Number(b) - Number(a))
    .slice(0, 2)
    .map(([key]) => humanizeKey(key));
  if (top.length && intent.rawText) items.push({ label: 'This request', value: top.join(', ') });
  return items;
}

export function confirmedSummary(profile: ShoppingDecisionProfile) {
  const rows: Array<{ key: string; label: string; level: PreferenceLevel; value: string; affectsRanking: boolean }> = [];
  const budget = profile.longTerm.usualBudgetRange?.max;
  if (budget != null) {
    rows.push({ key: 'budget_max', label: 'Typical Budget', level: 'important', value: `Usually under $${budget}`, affectsRanking: true });
  }
  for (const item of RANKING_PREFERENCES) {
    const weight = rankingWeightFor(profile, item.key);
    const level = preferenceLevel(weight);
    if (level === 'unspecified') continue;
    rows.push({ key: item.key, label: item.label, level, value: levelLabel(level), affectsRanking: true });
  }
  for (const style of profile.longTerm.shoppingStyle ?? []) {
    rows.push({ key: style, label: humanizeKey(style), level: 'important', value: 'Noted shopping habit', affectsRanking: false });
  }
  return rows;
}

export function inferredToRankingKey(key: string) {
  return INFERRED_TO_RANKING[key];
}

export function humanizeKey(value: string) {
  return value.replace(/_/g, ' ').replace(/([A-Z])/g, ' $1').replace(/\b\w/g, (letter) => letter.toUpperCase()).trim();
}

export function applyServerProfile(server: Record<string, any> | null | undefined, current: ShoppingDecisionProfile): ShoppingDecisionProfile {
  if (!server || typeof server !== 'object' || Array.isArray(server)) return current;
  const next: ShoppingDecisionProfile = structuredClone(current);
  const entries = Array.isArray(server.preferences) ? server.preferences : [];
  const confirmed = entries.filter((entry: any) => ['explicit', 'confirmed'].includes(String(entry.source)) && entry.scope !== 'observed' && entry.value !== 'dismissed');
  next.longTerm.stablePriorities = {};
  next.longTerm.usualBudgetRange = undefined;
  next.longTerm.shoppingStyle = [];
  for (const entry of confirmed) {
    const preference = String(entry.preference || '');
    if (preference === 'budget_max' && typeof entry.value === 'number') {
      next.longTerm.usualBudgetRange = { max: entry.value };
      continue;
    }
    if (preference === 'shopping_style' && typeof entry.value === 'string') {
      next.longTerm.shoppingStyle = Array.from(new Set([...(next.longTerm.shoppingStyle ?? []), entry.value]));
      continue;
    }
    if (typeof entry.weight === 'number') {
      next.longTerm.stablePriorities[clientKeyFromRanking(preference)] = entry.weight;
    }
  }
  if (server.budget_preference && server.budget_preference !== 'unknown') {
    next.longTerm.budgetPreference = server.budget_preference;
  }
  const dismissed = new Set(
    entries
      .filter((entry: any) => entry.value === 'dismissed' || (entry.scope === 'observed' && entry.value === 'dismissed'))
      .map((entry: any) => String(entry.preference)),
  );
  next.inferredPreferences = next.inferredPreferences.map((item) => (
    dismissed.has(item.key) ? { ...item, status: 'rejected' as const } : item
  ));
  for (const key of dismissed) {
    if (!next.inferredPreferences.some((item) => item.key === key)) {
      next.inferredPreferences.push({
        key,
        value: 'Dismissed by you',
        confidence: 1,
        evidence: ['You dismissed this inferred preference'],
        status: 'rejected',
      });
    }
  }
  next.lastUpdatedAt = new Date().toISOString();
  return next;
}

export function mergeRejectedInferences(profile: ShoppingDecisionProfile, inferred: InferredPreference[]) {
  const rejected = new Set(profile.inferredPreferences.filter((item) => item.status === 'rejected').map((item) => item.key));
  const confirmed = new Set(profile.inferredPreferences.filter((item) => item.status === 'confirmed').map((item) => item.key));
  return inferred.map((item) => {
    if (rejected.has(item.key)) return { ...item, status: 'rejected' as const };
    if (confirmed.has(item.key)) return { ...item, status: 'confirmed' as const };
    return item;
  });
}
