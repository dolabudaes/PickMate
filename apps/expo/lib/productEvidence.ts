import type { Product, ProductSourceFields, Review, StandardizedDimension, UserIntent } from '../types';

type DimensionKey = keyof UserIntent['softPreferences'];

const DIMENSION_LABELS: Record<string, string> = {
  noiseCancellation: 'Noise cancellation',
  comfort: 'Comfort',
  callQuality: 'Call quality',
  battery: 'Battery',
  priceValue: 'Price value',
  codecCompatibility: 'Compatibility',
  waterResistance: 'Water resistance',
  multipoint: 'Multipoint',
  quality: 'Quality',
  durability: 'Durability',
  reviewConfidence: 'Review confidence',
};

const KEYWORDS: Record<string, string[]> = {
  noiseCancellation: ['降噪', '安静', '地铁', 'noise cancel', 'noise-cancel', 'anc', 'quiet'],
  comfort: ['舒适', '舒服', '不胀', '小耳', '佩戴', 'comfortable', 'comfort', 'fit', 'ergonomic', 'soft'],
  callQuality: ['通话', '电话', '会议', '麦克风', 'call', 'microphone', 'voice', 'meeting'],
  battery: ['续航', '电池', 'battery', 'hours', 'charging', 'charge'],
  priceValue: ['性价比', '省钱', '便宜', '价格', 'value', 'affordable', 'budget', 'cheap'],
  codecCompatibility: ['兼容', '安卓', '苹果', 'android', 'ios', 'compatible', 'connector', 'bluetooth', 'ldac', 'lhdc'],
  waterResistance: ['防水', '出汗', 'waterproof', 'water resistant', 'sweat', 'ipx', 'ip54', 'ip55'],
  multipoint: ['多设备', '电脑', '平板', 'multipoint', 'multi-point', 'multi device'],
  quality: ['质量', '做工', '品质', '高质量', 'quality', 'well made', 'premium', 'sturdy'],
  durability: ['耐用', '耐久', '结实', '寿命', 'durable', 'durability', 'long lasting', 'sturdy', 'broken', 'broke'],
  reviewConfidence: ['评价', '评论', '口碑', 'reviews', 'rating', 'verified', 'helpful'],
};

export function sourceFieldsFor(product: Product): ProductSourceFields {
  if (product.sourceFields) return product.sourceFields;
  return {
    schema: 'unknown',
    productId: product.id,
    title: `${product.brand} ${product.name}`.trim(),
    mainCategory: product.category,
    store: product.sellerType,
    brand: product.brand,
    price: product.currentPrice,
    averageRating: product.rating,
    ratingNumber: product.reviewCount,
    features: product.positiveThemes,
    description: [product.description],
    details: {
      brand: product.brand,
      category: product.category,
      supportedCodecs: product.attributes.supportedCodecs,
      waterResistance: product.attributes.waterResistance,
      batteryHours: product.attributes.batteryHours,
    },
  };
}

export function searchableProductText(product: Product) {
  const source = sourceFieldsFor(product);
  return [
    source.title,
    source.mainCategory,
    source.store,
    source.brand,
    ...source.features,
    ...source.description,
    ...Object.entries(source.details).map(([key, value]) => `${key}: ${stringify(value)}`),
    product.description,
    product.positiveThemes.join(' '),
    product.negativeThemes.join(' '),
    product.reviews.map((review) => review.content).join(' '),
  ].join(' ').toLowerCase();
}

export function inferStandardizedDimensions(product: Product, intent?: UserIntent): Record<string, StandardizedDimension> {
  const keys = new Set<string>([
    ...Object.keys(KEYWORDS),
    ...(intent?.decisionDimensions ?? []),
    ...(intent?.explicitConcerns ?? []),
  ]);
  const out: Record<string, StandardizedDimension> = {};
  for (const key of keys) {
    const canonical = canonicalDimensionKey(key);
    out[canonical] = {
      key: canonical,
      label: DIMENSION_LABELS[canonical] ?? canonical,
      score: dimensionScore(product, canonical as DimensionKey, intent),
      polarity: dimensionPolarity(product, canonical),
      sources: dimensionSources(product, canonical),
      evidence: dimensionEvidence(product, canonical),
    };
  }
  return out;
}

export function dimensionScore(product: Product, key: DimensionKey | string, intent?: UserIntent) {
  const normalized = canonicalDimensionKey(key);
  const attrs = product.attributes;
  const ratingQuality = ratingScore(product);
  if (normalized === 'noiseCancellation') return attrs.noiseCancellationScore;
  if (normalized === 'comfort') return attrs.comfortScore;
  if (normalized === 'callQuality') return attrs.callScore;
  if (normalized === 'battery') return clamp(attrs.batteryHours * 8, 35, 100);
  if (normalized === 'codecCompatibility') return compatibilityScore(product, intent);
  if (normalized === 'waterResistance') return waterScore(attrs.waterResistance);
  if (normalized === 'multipoint') return attrs.multipoint ? 92 : 58;
  if (normalized === 'quality') return clamp(ratingQuality + keywordScore(product, KEYWORDS.quality) * 0.18, 35, 100);
  if (normalized === 'durability') return clamp((ratingQuality * 0.58) + (keywordScore(product, KEYWORDS.durability) * 0.42), 35, 100);
  if (normalized === 'reviewConfidence') return reviewConfidenceScore(product);
  return keywordScore(product, KEYWORDS[normalized] ?? [normalized]);
}

export function dimensionEvidence(product: Product, key: string) {
  const normalized = canonicalDimensionKey(key);
  const source = sourceFieldsFor(product);
  const snippets: string[] = [];
  const keywordSnippet = firstMatchingText(
    [
      ...source.features,
      ...source.description,
      ...Object.entries(source.details).map(([field, value]) => `${field}: ${stringify(value)}`),
    ],
    KEYWORDS[normalized] ?? [normalized],
  );
  if (keywordSnippet) snippets.push(keywordSnippet);
  const reviewSnippet = firstMatchingReview(product.reviews, KEYWORDS[normalized] ?? [normalized]);
  if (reviewSnippet) snippets.push(reviewSnippet);
  if (normalized === 'quality' || normalized === 'reviewConfidence') {
    snippets.push(`${product.rating.toFixed(1)} rating, ${product.reviewCount} reviews`);
  }
  return unique(snippets).slice(0, 3);
}

export function reviewSignals(product: Product, key?: string) {
  const keywords = key ? (KEYWORDS[canonicalDimensionKey(key)] ?? [key]) : [];
  const relevant = keywords.length
    ? product.reviews.filter((review) => containsAny(review.content, keywords))
    : product.reviews;
  const ranked = [...(relevant.length ? relevant : product.reviews)].sort((a, b) => reviewWeight(b) - reviewWeight(a));
  const positives = ranked.filter((review) => review.rating >= 4 || review.sentiment === 'positive').slice(0, 3);
  const concerns = ranked.filter((review) => review.rating <= 3 || review.sentiment === 'negative' || review.sentiment === 'mixed').slice(0, 3);
  return {
    positives,
    concerns,
    summary: summarizeReviews(positives, concerns),
  };
}

export function requiredTermCoverage(product: Product, intent: UserIntent) {
  const text = searchableProductText(product);
  const terms = intent.hardConstraints.requiredTerms ?? [];
  if (!terms.length) return { matched: [], missing: [] };
  const matched = terms.filter((term) => text.includes(term.toLowerCase()));
  const missing = terms.filter((term) => !text.includes(term.toLowerCase()));
  return { matched, missing };
}

export function requiredAttributeCoverage(product: Product, intent: UserIntent) {
  const source = sourceFieldsFor(product);
  const details = Object.fromEntries(Object.entries(source.details).map(([key, value]) => [key.toLowerCase(), stringify(value).toLowerCase()]));
  const required = intent.hardConstraints.requiredAttributes ?? [];
  const matched = required.filter((item) => {
    const direct = details[item.field.toLowerCase()];
    if (direct) return direct.includes(item.value.toLowerCase());
    return Object.entries(details).some(([field, value]) => field.includes(item.field.toLowerCase()) && value.includes(item.value.toLowerCase()));
  });
  return { matched, missing: required.filter((item) => !matched.includes(item)) };
}

export function productQualityLine(product: Product) {
  const source = sourceFieldsFor(product);
  const rating = source.averageRating ?? product.rating;
  const count = source.ratingNumber || product.reviewCount;
  if (!rating) return 'Rating data is insufficient; use product fields and review text instead.';
  return `${rating.toFixed(1)} rating from ${count} reviews`;
}

export function canonicalDimensionKey(key: string) {
  const map: Record<string, string> = {
    noise_cancellation: 'noiseCancellation',
    call_quality: 'callQuality',
    price_value: 'priceValue',
    compatibility: 'codecCompatibility',
    codec_compatibility: 'codecCompatibility',
    water_resistance: 'waterResistance',
    review_confidence: 'reviewConfidence',
    risk_attention: 'durability',
    comfort_attention: 'comfort',
    price_attention: 'priceValue',
  };
  return map[key] ?? key;
}

function summarizeReviews(positives: Review[], concerns: Review[]) {
  const positive = positives[0]?.content;
  const concern = concerns[0]?.content;
  if (positive && concern) return `Positive review mentions: ${positive}; concern focuses on: ${concern}`;
  if (positive) return `Positive review mentions: ${positive}`;
  if (concern) return `Concern focuses on: ${concern}`;
  return 'Not enough relevant review text found.';
}

function dimensionPolarity(product: Product, key: string): StandardizedDimension['polarity'] {
  const signals = reviewSignals(product, key);
  if (signals.positives.length && signals.concerns.length) return 'mixed';
  if (signals.positives.length) return 'positive';
  if (signals.concerns.length) return 'negative';
  return 'unknown';
}

function dimensionSources(product: Product, key: string): StandardizedDimension['sources'] {
  const source = sourceFieldsFor(product);
  const sources: StandardizedDimension['sources'] = [];
  const fields = [...source.features, ...source.description, ...Object.keys(source.details)];
  if (firstMatchingText([source.title], KEYWORDS[key] ?? [key])) sources.push('title');
  if (firstMatchingText(fields, KEYWORDS[key] ?? [key])) sources.push('features', 'details');
  if (product.reviews.some((review) => containsAny(review.content, KEYWORDS[key] ?? [key]))) sources.push('review');
  if (key === 'quality' || key === 'reviewConfidence') sources.push('rating');
  return unique(sources).slice(0, 4);
}

function keywordScore(product: Product, keywords: string[]) {
  const text = searchableProductText(product);
  const hits = keywords.filter((keyword) => text.includes(keyword.toLowerCase())).length;
  const reviewHits = product.reviews.filter((review) => containsAny(review.content, keywords)).length;
  return clamp(58 + hits * 7 + Math.min(reviewHits, 6) * 5, 35, 96);
}

function compatibilityScore(product: Product, intent?: UserIntent) {
  const attrs = product.attributes;
  const text = searchableProductText(product);
  if (intent?.hardConstraints.devicePlatform === 'android') {
    if (attrs.supportedCodecs.some((codec) => ['LDAC', 'LHDC', 'SSC', 'L2HC'].includes(codec))) return 95;
    if (attrs.androidCompatible || /android|安卓|compatible/.test(text)) return 78;
    return 50;
  }
  if (intent?.hardConstraints.devicePlatform === 'ios') {
    if (attrs.iosCompatible || /iphone|ios|苹果/.test(text)) return 84;
    return 58;
  }
  return /compatible|兼容/.test(text) ? 82 : 72;
}

function ratingScore(product: Product) {
  const rating = product.rating || sourceFieldsFor(product).averageRating || 0;
  const reviewCount = product.reviewCount || sourceFieldsFor(product).ratingNumber || 0;
  const confidence = Math.min(10, Math.log10(Math.max(reviewCount, 1)) * 3);
  return clamp(rating * 18 + confidence, 35, 100);
}

function reviewConfidenceScore(product: Product) {
  const source = sourceFieldsFor(product);
  const countScore = Math.min(42, Math.log10(Math.max(source.ratingNumber || product.reviewCount, 1)) * 14);
  const verified = product.reviews.filter((review) => review.verifiedPurchase).length;
  const helpful = product.reviews.reduce((sum, review) => sum + review.helpfulCount, 0);
  return clamp(42 + countScore + Math.min(10, verified) + Math.min(8, helpful / 50), 35, 100);
}

function firstMatchingReview(reviews: Review[], keywords: string[]) {
  const review = [...reviews]
    .filter((item) => containsAny(item.content, keywords))
    .sort((a, b) => reviewWeight(b) - reviewWeight(a))[0];
  if (!review) return '';
  const proof = review.verifiedPurchase ? 'Verified purchase' : 'Review';
  return `${proof} ${review.rating} stars: ${review.content}`;
}

function firstMatchingText(values: string[], keywords: string[]) {
  const value = values.find((item) => containsAny(item, keywords));
  return value ? truncate(value, 96) : '';
}

function containsAny(text: string, keywords: string[]) {
  const lower = text.toLowerCase();
  return keywords.some((keyword) => lower.includes(keyword.toLowerCase()));
}

function reviewWeight(review: Review) {
  return review.helpfulCount + (review.verifiedPurchase ? 8 : 0) + review.rating * 2;
}

function waterScore(value: string) {
  return value.includes('7') ? 95 : value.includes('5') ? 82 : value.includes('4') ? 70 : 55;
}

function stringify(value: unknown): string {
  if (Array.isArray(value)) return value.map(stringify).join(', ');
  if (value && typeof value === 'object') return Object.entries(value).map(([key, nested]) => `${key}: ${stringify(nested)}`).join(', ');
  return String(value ?? '');
}

function truncate(value: string, max: number) {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

function unique<T>(values: T[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}
