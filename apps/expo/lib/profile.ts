import type {
  BrowsingContext,
  BrowsingEvent,
  DecisionContext,
  DevicePlatform,
  InferredPreference,
  ShoppingDecisionProfile,
  UserIntent,
} from '../types';

export const defaultShoppingDecisionProfile: ShoppingDecisionProfile = {
  session: {
    useCases: [],
    priorities: {},
    explicitConcerns: [],
    dealbreakers: [],
    acceptedTradeoffs: [],
    viewedProductIds: [],
    comparedProductIds: [],
    savedProductIds: [],
    chosenProductIds: [],
    rejectedProductIds: [],
  },
  longTerm: {
    devicePreferences: [],
    stablePriorities: {},
    budgetPreference: 'unknown',
    confirmedTradeoffs: [],
    shoppingStyle: [],
  },
  inferredPreferences: [],
  lastUpdatedAt: new Date().toISOString(),
};

export function buildDecisionContext(intent: UserIntent, events: BrowsingEvent[], profile: ShoppingDecisionProfile): DecisionContext {
  const browsingContext = buildBrowsingContext(events);
  const inferred = mergeInferredPreferences(profile.inferredPreferences, inferPreferencesFromBehavior(events));
  return {
    currentIntent: intent,
    browsingContext,
    sessionProfile: {
      ...profile.session,
      budget: { min: intent.budget.min ?? undefined, max: intent.budget.max ?? undefined },
      useCases: intent.useCases,
      devicePlatform: intent.hardConstraints.devicePlatform,
      priorities: { ...profile.session.priorities, ...intent.softPreferences },
      explicitConcerns: Array.from(new Set([...profile.session.explicitConcerns, ...intent.explicitConcerns])),
      dealbreakers: Array.from(new Set([...profile.session.dealbreakers, ...intent.dealbreakers])),
      acceptedTradeoffs: profile.session.acceptedTradeoffs,
      viewedProductIds: unique([...browsingContext.viewedProductIds, ...(profile.session.viewedProductIds ?? [])]),
      comparedProductIds: unique([...browsingContext.comparedProductIds, ...(profile.session.comparedProductIds ?? [])]),
      savedProductIds: profile.session.savedProductIds ?? [],
      chosenProductIds: profile.session.chosenProductIds ?? [],
      rejectedProductIds: profile.session.rejectedProductIds ?? [],
    },
    confirmedLongTermProfile: profile.longTerm,
    relevantInferredPreferences: inferred.filter((item) => item.status === 'inferred'),
    profileSnapshot: { ...profile, inferredPreferences: inferred, lastUpdatedAt: profile.lastUpdatedAt },
  };
}

export function inferPreferencesFromBehavior(events: BrowsingEvent[]): InferredPreference[] {
  const priceOpenCount = events.filter((event) => event.name === 'price_history_opened').length;
  const reviewRiskCount = events.filter((event) => ['negative_reviews_opened', 'video_evidence_opened'].includes(event.name)).length;
  const comfortCount = events.filter((event) => ['reviews_opened', 'video_evidence_opened', 'product_detail_section_opened'].includes(event.name)).length;
  const inferred: InferredPreference[] = [];
  if (priceOpenCount >= 2) inferred.push({
    key: 'price_attention',
    value: 'Recently checked price changes several times',
    confidence: Math.min(0.82, 0.48 + priceOpenCount * 0.09),
    evidence: ['Opened price history several times'],
    status: 'inferred',
  });
  if (comfortCount >= 3) inferred.push({
    key: 'comfort_attention',
    value: 'Recently focused on fit and use experience',
    confidence: Math.min(0.86, 0.5 + comfortCount * 0.07),
    evidence: ['Viewed reviews, specs, or fit-related videos'],
    status: 'inferred',
  });
  if (reviewRiskCount >= 2) inferred.push({
    key: 'risk_attention',
    value: 'Recently focused on negative reviews and video issues',
    confidence: Math.min(0.84, 0.52 + reviewRiskCount * 0.08),
    evidence: ['Viewed negative reviews or video evidence'],
    status: 'inferred',
  });
  const comparedCount = events.filter((event) => event.name === 'product_added_to_compare').length;
  if (comparedCount >= 2) inferred.push({
    key: 'comparison_style',
    value: 'Recently tends to compare before deciding',
    confidence: Math.min(0.78, 0.45 + comparedCount * 0.08),
    evidence: ['Added products to compare several times'],
    status: 'inferred',
  });
  const purchaseIntentCount = events.filter((event) => ['add_to_cart_after_picki', 'purchase_intent_after_picki'].includes(event.name)).length;
  if (purchaseIntentCount >= 1) inferred.push({
    key: 'decision_confidence',
    value: 'More likely to move forward after seeing recommendation evidence',
    confidence: Math.min(0.76, 0.58 + purchaseIntentCount * 0.08),
    evidence: ['Cart or purchase intent after Picki recommendation'],
    status: 'inferred',
  });
  return inferred;
}

export function handleProfileUpdate(text: string, profile: ShoppingDecisionProfile) {
  const normalized = text.toLowerCase();
  const next = structuredClone(profile);
  const isLongTerm = /以后|以后买|长期|都放第一|一直/.test(text);
  const isSessionOnly = /这次|现在|本次|不要根据这次|临时/.test(text) || !isLongTerm;
  let changed = false;
  let message = '';

  if (/from now on|always|long[- ]term|usually/.test(normalized) && /comfort/.test(normalized)) {
    next.longTerm.stablePriorities.comfort = 0.92;
    changed = true;
    message = 'Saved comfort as a confirmed long-term preference.';
  }
  if (/不太在意价格|价格不重要|不用太便宜/.test(text)) {
    if (isLongTerm) next.longTerm.priceSensitivity = 0.25;
    else next.session.priorities.priceValue = 0.18;
    next.longTerm.budgetPreference = isLongTerm ? 'quality_first' : next.longTerm.budgetPreference;
    changed = true;
    message = isLongTerm ? 'Saved “price is not the top factor” as a long-term preference.' : 'Lowered price weight for this shopping session only.';
  }
  if (/舒适.*第一|更在意舒适|戴久|不胀/.test(text)) {
    if (isLongTerm) next.longTerm.stablePriorities.comfort = 0.92;
    else next.session.priorities.comfort = 0.95;
    changed = true;
    message = isLongTerm ? 'Saved “comfort first” as a long-term preference.' : 'Raised comfort weight for this shopping session only.';
  }
  if (/不.*在意通话|通话不重要|很少打电话/.test(text)) {
    if (isLongTerm) next.longTerm.stablePriorities.callQuality = 0.18;
    else next.session.priorities.callQuality = 0.12;
    changed = true;
    message = isLongTerm ? 'Saved “call quality is not a long-term priority” as a long-term preference.' : 'Lowered call-quality weight for this shopping session only.';
  }
  if (/这次.*降噪|只想.*降噪|降噪最强|更在意降噪/.test(text)) {
    next.session.priorities.noiseCancellation = 1;
    next.session.priorities.comfort = Math.min(next.session.priorities.comfort ?? 0.5, 0.45);
    changed = true;
    message = 'Prioritized this explicit session need: focus on noise cancellation first.';
  }
  if (/可以到\s*(\d{3,4})|预算.*(\d{3,4})/.test(text)) {
    const match = text.match(/(\d{3,4})/);
    if (match) {
      next.session.budget = { ...next.session.budget, max: Number(match[1]) };
      changed = true;
      message = 'Updated this shopping session budget only.';
    }
  }
  if (/确认.*价格|价格.*是这样/.test(text)) changed = confirmInference(next, 'price_attention');
  if (/确认.*舒适|舒适.*是这样/.test(text)) changed = confirmInference(next, 'comfort_attention');
  if (/确认.*风险|风险.*是这样/.test(text)) changed = confirmInference(next, 'risk_attention');
  if (/确认.*比较|比较.*是这样/.test(text)) changed = confirmInference(next, 'comparison_style');
  if (/确认.*质量|品质.*第一|质量.*第一/.test(text)) {
    next.longTerm.stablePriorities.quality = 0.88;
    next.longTerm.reliabilityPreference = Math.max(next.longTerm.reliabilityPreference ?? 0.5, 0.8);
    changed = true;
    message = 'Saved “quality/reputation first” as a long-term preference.';
  }
  if (/不是这样|不对|不要记住/.test(text)) {
    next.inferredPreferences = next.inferredPreferences.map((item) => item.status === 'inferred' ? { ...item, status: 'rejected' } : item);
    changed = true;
    message = 'Marked recent inferences as not applicable; they will not be saved long term.';
  }

  if (changed) next.lastUpdatedAt = new Date().toISOString();
  return { profile: next, changed, scope: isSessionOnly ? 'session' : 'long_term', message };
}

export function updateInferredPreference(profile: ShoppingDecisionProfile, key: string, status: InferredPreference['status']) {
  const next = structuredClone(profile);
  next.inferredPreferences = next.inferredPreferences.map((item) => item.key === key ? { ...item, status } : item);
  if (status === 'confirmed') applyConfirmedPreference(next, key);
  next.lastUpdatedAt = new Date().toISOString();
  return next;
}

export function deleteProfilePreference(profile: ShoppingDecisionProfile, key: string) {
  const next = structuredClone(profile);
  delete next.session.priorities[key];
  delete next.longTerm.stablePriorities[key];
  next.inferredPreferences = next.inferredPreferences.filter((item) => item.key !== key);
  next.longTerm.confirmedTradeoffs = next.longTerm.confirmedTradeoffs.filter((item) => !item.includes(labelForPreference(key)));
  next.lastUpdatedAt = new Date().toISOString();
  return next;
}

function buildBrowsingContext(events: BrowsingEvent[]): BrowsingContext {
  const viewedProductIds = unique(events.filter((event) => event.name === 'product_viewed').map((event) => event.productId).filter(Boolean) as string[]);
  const comparedProductIds = unique(events.filter((event) => event.name === 'product_added_to_compare').map((event) => event.productId).filter(Boolean) as string[]);
  const openedEvidenceTypes = unique(events.filter((event) => event.name.endsWith('_opened')).map((event) => event.name.replace('_opened', '')));
  return {
    viewedProductIds,
    comparedProductIds,
    openedEvidenceTypes,
    signals: openedEvidenceTypes.map((type) => ({ key: `${type}_attention`, source: 'browsing', label: `Recently viewed ${type}` })),
  };
}

function mergeInferredPreferences(existing: InferredPreference[], incoming: InferredPreference[]) {
  const map = new Map(existing.map((item) => [item.key, item]));
  for (const item of incoming) {
    const current = map.get(item.key);
    if (current?.status === 'rejected' || current?.status === 'confirmed') continue;
    if (!current || (current.status === 'inferred' && item.confidence > current.confidence)) map.set(item.key, item);
  }
  return [...map.values()];
}

function confirmInference(profile: ShoppingDecisionProfile, key: string) {
  profile.inferredPreferences = profile.inferredPreferences.map((item) => item.key === key ? { ...item, status: 'confirmed' } : item);
  applyConfirmedPreference(profile, key);
  return true;
}

function applyConfirmedPreference(profile: ShoppingDecisionProfile, key: string) {
  if (key === 'price_attention') profile.longTerm.priceSensitivity = Math.max(profile.longTerm.priceSensitivity ?? 0.5, 0.72);
  if (key === 'comfort_attention') profile.longTerm.stablePriorities.comfort = Math.max(profile.longTerm.stablePriorities.comfort ?? 0.5, 0.78);
  if (key === 'risk_attention') profile.longTerm.reliabilityPreference = Math.max(profile.longTerm.reliabilityPreference ?? 0.5, 0.78);
  if (key === 'comparison_style') profile.longTerm.shoppingStyle = unique([...(profile.longTerm.shoppingStyle ?? []), 'likes_comparing']);
  if (key === 'decision_confidence') profile.longTerm.shoppingStyle = unique([...(profile.longTerm.shoppingStyle ?? []), 'evidence_moves_to_action']);
}

function labelForPreference(key: string) {
  return ({ priceValue: 'Price', comfort: 'Comfort', callQuality: 'Calls', noiseCancellation: 'Noise cancellation', quality: 'Quality', durability: 'Durability' } as Record<string, string>)[key] ?? key;
}

function unique<T>(values: T[]) {
  return Array.from(new Set(values));
}
