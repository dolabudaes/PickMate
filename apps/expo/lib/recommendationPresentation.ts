import type { PickiProductRef, StructuredPickiResponse } from './shoppingTurn';

export type RecommendationRefGroup = {
  primary?: PickiProductRef;
  alternatives: PickiProductRef[];
};

export function structuredComparisonLayout(isMobile: boolean) {
  return isMobile
    ? { direction: 'column' as const, cardWidth: '100%' as const, truncateText: false }
    : { direction: 'row' as const, cardWidth: 'auto' as const, truncateText: true };
}

export function groupRecommendationRefs(refs?: PickiProductRef[] | null): RecommendationRefGroup {
  if (!refs?.length) return { primary: undefined, alternatives: [] };

  const primary = refs.find((ref) => ref.role === 'primary') ?? refs[0];
  const seen = new Set([refKey(primary)]);
  const alternatives: PickiProductRef[] = [];

  for (const ref of refs) {
    const key = refKey(ref);
    if (seen.has(key)) continue;
    seen.add(key);
    alternatives.push(ref);
    if (alternatives.length === 2) break;
  }

  return { primary, alternatives };
}

export function shouldUseRecommendationCards(response: StructuredPickiResponse) {
  return response.responseType === 'RECOMMENDATION' && Boolean(groupRecommendationRefs(response.productRefs).primary);
}

export function visibleSuggestedActions<T>(actions?: T[] | null): T[] {
  return (actions ?? []).slice(0, 2);
}

function refKey(ref: PickiProductRef) {
  if (ref.productId) return `id:${ref.productId}`;
  if (ref.title) return `title:${ref.title.trim().toLocaleLowerCase()}`;
  return `ref:${ref.role ?? ''}:${ref.brand ?? ''}:${ref.price ?? ''}:${ref.specLine ?? ''}`;
}
