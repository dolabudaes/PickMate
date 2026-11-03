import { reviewSignals } from './productEvidence';
import { humanizeText } from './presentation';
import type { Product, RecommendationProduct, UserIntent } from '../types';

export type ProductAnalysis = {
  verdict: string;
  advantages: string[];
  disadvantages: string[];
};

export function buildProductAnalysis(
  product: Product,
  intent?: UserIntent,
  insight?: RecommendationProduct | null,
): ProductAnalysis {
  const advantages: string[] = [];
  const disadvantages: string[] = [];

  if (insight?.product.id === product.id) {
    advantages.push(...insight.reasons.filter(Boolean).slice(0, 4));
    disadvantages.push(...insight.cautions.filter(Boolean).slice(0, 3));
    for (const risk of insight.relevantRisks.slice(0, 2)) {
      const line = risk.detail || risk.title;
      if (line) disadvantages.push(line);
    }
    if (insight.regretGuard) disadvantages.push(insight.regretGuard);
    for (const item of insight.evidence.slice(0, 2)) {
      if (item.detail) advantages.push(item.detail);
    }
  }

  const signals = reviewSignals(product);
  for (const review of signals.positives.slice(0, 2)) {
    advantages.push(trimQuote(review.content, 110));
  }
  for (const review of signals.concerns.slice(0, 2)) {
    disadvantages.push(trimQuote(review.content, 110));
  }

  for (const theme of product.positiveThemes.slice(0, 2)) advantages.push(theme);
  for (const theme of product.negativeThemes.slice(0, 2)) disadvantages.push(theme);

  const source = product.sourceFields;
  for (const feature of source?.features?.slice(0, 2) ?? []) {
    advantages.push(feature);
  }

  if (intent?.budget.max != null && product.currentPrice > intent.budget.max) {
    disadvantages.push(`The current price is above your budget limit of ${intent.budget.max}.`);
  } else if (intent?.budget.max != null && product.currentPrice <= intent.budget.max * 0.85) {
    advantages.push('The price fits your budget with room to spare.');
  }

  const rating = product.rating || product.sourceFields?.averageRating;
  const count = product.reviewCount || product.sourceFields?.ratingNumber || 0;
  const verdict = insight?.reasons[0]
    || (rating
      ? `Picki reviewed the specifications and ${formatCount(count)} review signals for this product.`
      : 'Picki summarized the available product fields and reviews; some information may be missing.');

  return {
    verdict: humanizeText(verdict),
    advantages: dedupe(advantages).map(humanizeText).slice(0, 5),
    disadvantages: dedupe(disadvantages).map(humanizeText).slice(0, 5),
  };
}

function trimQuote(text: string, max = 96) {
  const clean = text.replace(/\s+/g, ' ').trim();
  if (!clean) return '';
  return clean.length <= max ? clean : `${clean.slice(0, max - 1)}…`;
}

function formatCount(count: number) {
  if (count >= 1000000) return `${(count / 1000000).toFixed(1)}m`;
  if (count >= 1000) return `${(count / 1000).toFixed(1)}k`;
  return `${count}`;
}

function dedupe(items: string[]) {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const item of items) {
    const key = item.trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(key);
  }
  return out;
}
