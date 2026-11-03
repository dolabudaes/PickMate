import { displayPrice, productTitle } from './format';
import type { Product, RecommendationResult } from '../types';

export function verifiedFacts(product: Product) {
  const facts: string[] = [];
  const category = product.sourceFields?.mainCategory || product.category;
  if (category) facts.push(category);
  if (product.brand) facts.push(product.brand);
  if (!(product.sourceFields && product.sourceFields.price == null)) facts.push(displayPrice(product));
  if (product.rating) facts.push(`${product.rating.toFixed(1)} stars from ${product.reviewCount.toLocaleString()} reviews`);
  const feature = product.sourceFields?.features?.find((item) => item.trim().length > 8);
  if (feature) facts.push(feature);
  return facts.slice(0, 5);
}

export function productTypeHint(product: Product) {
  const text = `${productTitle(product)} ${(product.sourceFields?.features || []).join(' ')}`.toLowerCase();
  if (/sound\s*bar/.test(text)) return 'Soundbar';
  if (/\bspeakers?\b/.test(text)) return 'Speaker';
  if (/\breceivers?\b/.test(text)) return 'Receiver';
  if (/amplifier|\bamp\b/.test(text)) return 'Amplifier';
  if (/home\s*theat|surround/.test(text)) return 'Home theater';
  if (/hdmi|optical|toslink|cable/.test(text)) return 'Cable / accessory';
  if (/headphone|earbud|headset/.test(text)) return 'Headphones';
  return product.category || 'Home audio';
}

export function unknownChecks(product: Product, need: string, result: RecommendationResult | null) {
  const checks: string[] = [];
  const blob = `${productTitle(product)} ${JSON.stringify(product.sourceFields?.details || {})} ${(product.sourceFields?.features || []).join(' ')}`.toLowerCase();
  const asked = need.toLowerCase();
  if (/hdmi|arc|earc/.test(asked) && !/hdmi|arc|earc/.test(blob)) checks.push('HDMI / ARC support is not verified in the catalog.');
  if (/tv|television/.test(asked) && !/hdmi|optical|bluetooth/.test(blob)) checks.push('TV compatibility needs confirmation from the listing or your ports.');
  if (result?.primaryRecommendation?.regretGuard) checks.push(result.primaryRecommendation.regretGuard);
  else if (result?.regretGuard) checks.push(String(result.regretGuard));
  if (result?.missingInformation?.[0]) checks.push(result.missingInformation[0]);
  if (!product.reviews?.length) checks.push('Review text was not loaded for this product.');
  return [...new Set(checks.filter(Boolean))].slice(0, 3);
}
