import { buildProductAnalysis } from './productBrief';
import { displayPrice, productTitle } from './format';
import { humanizeText } from './presentation';
import type { Product, RecommendationProduct, RecommendationResult, UserIntent } from '../types';

export type DecisionStance = 'buy' | 'conditional' | 'skip' | 'unknown';

export type DecisionBrief = {
  stance: DecisionStance;
  stanceLabel: string;
  headline: string;
  subject: string;
  price: string;
  fit: Array<{ label: string; ok: boolean; detail: string }>;
  pros: string[];
  cons: string[];
  priceTake: string;
  regret: string;
  alternative?: string;
  missing: string[];
  followUps: string[];
};

export function buildDecisionBrief(result: RecommendationResult, focusProduct?: Product): DecisionBrief | null {
  const insight = pickInsight(result, focusProduct);
  const product = focusProduct ?? insight?.product;
  if (!product) return null;
  const analysis = buildProductAnalysis(product, result.parsedIntent, insight);
  const stance = stanceFor(analysis, result.parsedIntent, product);
  return {
    stance,
    stanceLabel: stanceLabel(stance),
    headline: analysis.verdict,
    subject: productTitle(product),
    price: displayPrice(product),
    fit: fitRows(product, result.parsedIntent),
    pros: analysis.advantages.slice(0, 3),
    cons: analysis.disadvantages.slice(0, 3),
    priceTake: humanizeText(insight?.priceAnalysis.explanation || priceFallback(product, result.parsedIntent)),
    regret: humanizeText(insight?.regretGuard || result.regretGuard || analysis.disadvantages[0] || 'The recommendation may change if your needs change.'),
    alternative: alternativeLine(result, product.id),
    missing: (result.missingInformation ?? []).map(humanizeText).slice(0, 2),
    followUps: followUps(focusProduct, result.parsedIntent),
  };
}

function pickInsight(result: RecommendationResult, focusProduct?: Product): RecommendationProduct | null {
  if (focusProduct) {
    if (result.primaryRecommendation?.product.id === focusProduct.id) return result.primaryRecommendation;
    return result.alternatives.find((item) => item.product.id === focusProduct.id) ?? result.primaryRecommendation;
  }
  return result.primaryRecommendation;
}

function stanceFor(analysis: ReturnType<typeof buildProductAnalysis>, intent: UserIntent, product: Product): DecisionStance {
  const overBudget = intent.budget.max != null && product.currentPrice > intent.budget.max;
  if (overBudget || (analysis.disadvantages.length >= 3 && analysis.advantages.length <= 1)) return 'skip';
  if (!analysis.advantages.length && !analysis.disadvantages.length) return 'unknown';
  if (analysis.disadvantages.length) return 'conditional';
  return 'buy';
}

function stanceLabel(stance: DecisionStance) {
  if (stance === 'buy') return 'Top pick';
  if (stance === 'conditional') return 'Good fit with conditions';
  if (stance === 'skip') return 'Skip for now';
  return 'Not enough evidence';
}

function fitRows(product: Product, intent: UserIntent) {
  const rows: DecisionBrief['fit'] = [];
  const raw = intent.rawText || '';
  const budgetMentioned = /\d/.test(raw) && /预算|以内|\$|块|元|usd|budget/i.test(raw);
  if (budgetMentioned && intent.budget.max != null) {
    const ok = product.currentPrice <= intent.budget.max;
    rows.push({
      label: 'Budget',
      ok,
      detail: ok ? `${displayPrice(product)} is within ${intent.budget.max}` : `${displayPrice(product)} exceeds ${intent.budget.max}`,
    });
  }
  const sceneMentioned = /通勤|地铁|运动|办公|游戏|睡觉|scene|通勤|日常/i.test(raw);
  if (sceneMentioned && intent.useCases[0]) {
    const text = searchable(product);
    const ok = intent.useCases.some((item) => text.includes(item.toLowerCase())) || Boolean(product.bestFor.length);
    rows.push({ label: 'Use case', ok, detail: intent.useCases.slice(0, 2).map(humanizeText).join(', ') });
  }
  const terms = intent.hardConstraints.requiredTerms ?? [];
  if (terms.length) {
    const text = searchable(product);
    const hit = terms.filter((term) => text.includes(term.toLowerCase()));
    rows.push({
      label: 'Hard requirements',
      ok: hit.length === terms.length,
      detail: hit.length ? `Matched: ${hit.slice(0, 3).join(', ')}` : `Not found in the product data: ${terms.slice(0, 3).join(', ')}`,
    });
  }
  if (intent.explicitConcerns[0]) {
    rows.push({
      label: 'Your concern',
      ok: true,
      detail: intent.explicitConcerns.slice(0, 2).map(humanizeText).join(', '),
    });
  }
  return rows.slice(0, 4);
}

function searchable(product: Product) {
  const source = product.sourceFields;
  return [
    product.name,
    product.description,
    source?.title,
    ...(source?.features ?? []),
    ...(source?.description ?? []),
    ...product.positiveThemes,
    ...product.reviews.map((review) => review.content),
  ].join(' ').toLowerCase();
}

function priceFallback(product: Product, intent: UserIntent) {
  if (intent.budget.max != null && product.currentPrice > intent.budget.max) return 'The current price is above your stated budget.';
  if (product.sourceFields?.price == null) return 'Price data is incomplete; verify the listing before deciding.';
  return `${displayPrice(product)}; use the rating and review evidence to judge the value.`;
}

function alternativeLine(result: RecommendationResult, currentId: string) {
  const alt = result.alternatives.find((item) => item.product.id !== currentId) ?? result.alternatives[0];
  if (!alt || alt.product.id === currentId) return undefined;
  const why = humanizeText(alt.reasons[0] || alt.cautions[0] || '');
  return why ? `If another factor matters more, consider ${productTitle(alt.product)}: ${why}` : `If this is not a fit, consider ${productTitle(alt.product)}.`;
}

function followUps(focusProduct: Product | undefined, intent: UserIntent) {
  if (focusProduct) {
    return ['Is it worth this price?', 'What do the negative reviews say?', 'Who might regret buying it?'];
  }
  if (intent.budget.max) return ['Is there a cheaper option?', 'Which choice is safer?', 'What are the main risks?'];
  return ['What is your budget?', 'How will you use it?', 'What would be a dealbreaker?'];
}
