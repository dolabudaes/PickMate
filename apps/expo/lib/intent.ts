import type { UserIntent } from '../types';

const evenPreferences = {
  noiseCancellation: 0.5,
  comfort: 0.5,
  callQuality: 0.5,
  battery: 0.5,
  priceValue: 0.5,
  codecCompatibility: 0.5,
  waterResistance: 0.5,
  multipoint: 0.5,
  quality: 0.5,
  durability: 0.5,
  reviewConfidence: 0.5,
};

export const blankIntent: UserIntent = {
  category: 'any',
  budget: { min: null, max: null },
  hardConstraints: { inStock: false, devicePlatform: 'any', formFactor: null, brandOrStore: null, requiredTerms: [], requiredAttributes: [] },
  useCases: [],
  softPreferences: { ...evenPreferences },
  fitNeeds: { smallEarFriendly: false, avoidDeepInsertion: false },
  dealbreakers: [],
  explicitConcerns: [],
  missingCriticalInformation: [],
  productQuery: '',
  reviewEvidenceNeeds: [],
  decisionDimensions: [],
  rawText: '',
};

export const defaultIntent = blankIntent;

export function parseIntent(text: string, previous: UserIntent = blankIntent): UserIntent {
  const next: UserIntent = structuredClone(previous);
  next.rawText = text || previous.rawText;
  next.explicitConcerns = [...previous.explicitConcerns];
  next.dealbreakers = [...previous.dealbreakers];
  next.useCases = [...previous.useCases];
  next.hardConstraints = {
    ...previous.hardConstraints,
    requiredTerms: [...(previous.hardConstraints.requiredTerms ?? [])],
    requiredAttributes: [...(previous.hardConstraints.requiredAttributes ?? [])],
  };
  next.reviewEvidenceNeeds = [...(previous.reviewEvidenceNeeds ?? [])];
  next.decisionDimensions = [...(previous.decisionDimensions ?? [])];
  const normalized = text.toLowerCase();
  const budget = extractBudget(text);
  if (budget != null) next.budget.max = budget;
  const category = inferCategory(text);
  if (category) next.category = category;
  const productQuery = extractProductQuery(text);
  if (productQuery) next.productQuery = productQuery;
  const brandOrStore = extractBrandOrStore(text);
  if (brandOrStore) next.hardConstraints.brandOrStore = brandOrStore;
  if (/安卓|android/.test(normalized)) next.hardConstraints.devicePlatform = 'android';
  if (/苹果|iphone|ios/.test(normalized)) next.hardConstraints.devicePlatform = 'ios';
  if (/半入耳/.test(text)) next.hardConstraints.formFactor = 'semi_in_ear';
  if (/入耳/.test(text) && !/半入耳/.test(text)) next.hardConstraints.formFactor = 'in_ear';
  if (/地铁|通勤|公交|地铁/.test(text) && !next.useCases.includes('subway_commute')) next.useCases.push('subway_commute');
  if (/运动|跑步|健身/.test(text)) next.useCases.push('sports');
  if (/办公|办公室|office|work|商务|business/.test(normalized)) next.useCases.push('office');
  if (/旅行|差旅|travel|trip/.test(normalized)) next.useCases.push('travel');
  if (/电话|会议|通话|开会/.test(text)) {
    next.softPreferences.callQuality = 0.95;
    next.softPreferences.noiseCancellation *= 0.72;
    next.explicitConcerns.push('call_quality');
    next.decisionDimensions.push('callQuality');
  }
  if (/耳朵疼|戴久|舒服|舒适|不胀/.test(text)) {
    next.softPreferences.comfort = 0.95;
    next.fitNeeds.smallEarFriendly = true;
    next.explicitConcerns.push('comfort');
    next.decisionDimensions.push('comfort');
  }
  if (/降噪|地铁太吵|安静|noise cancel|anc/.test(normalized)) {
    next.softPreferences.noiseCancellation = 0.95;
    next.decisionDimensions.push('noiseCancellation');
  }
  if (/续航|电池|battery/.test(normalized)) {
    next.softPreferences.battery = 0.85;
    next.decisionDimensions.push('battery');
  }
  if (/便宜|性价比|省钱|预算|value|budget|affordable|cheap/.test(normalized)) {
    next.softPreferences.priceValue = 0.9;
    next.decisionDimensions.push('priceValue');
  }
  if (/不喜欢.*深|不要.*深|塞得很深/.test(text)) {
    next.fitNeeds.avoidDeepInsertion = true;
    next.explicitConcerns.push('avoid_deep_insertion');
  }
  if (/防水|出汗|waterproof|water resistant|sweat/.test(normalized)) {
    next.softPreferences.waterResistance = 0.8;
    next.decisionDimensions.push('waterResistance');
  }
  if (/多设备|电脑|平板|multipoint|multi device/.test(normalized)) {
    next.softPreferences.multipoint = 0.8;
    next.decisionDimensions.push('multipoint');
  }
  if (/兼容|适配|compatible|compatibility|connector|型号|model/.test(normalized)) {
    next.softPreferences.codecCompatibility = 0.88;
    next.explicitConcerns.push('compatibility');
    next.decisionDimensions.push('codecCompatibility');
  }
  if (/质量|品质|做工|好评|评分|口碑|quality|rating|reviews?|stars?/.test(normalized)) {
    next.softPreferences.quality = 0.86;
    next.softPreferences.reviewConfidence = 0.78;
    next.explicitConcerns.push('quality');
    next.decisionDimensions.push('quality', 'reviewConfidence');
  }
  if (/耐用|耐久|结实|坏|寿命|durable|durability|long lasting|sturdy/.test(normalized)) {
    next.softPreferences.durability = 0.86;
    next.explicitConcerns.push('durability');
    next.decisionDimensions.push('durability');
  }
  next.hardConstraints.requiredAttributes = mergeRequiredAttributes(next.hardConstraints.requiredAttributes ?? [], extractRequiredAttributes(text));
  next.reviewEvidenceNeeds = unique([...next.reviewEvidenceNeeds, ...extractReviewEvidenceNeeds(text)]);
  next.decisionDimensions = unique(next.decisionDimensions.map(canonicalDimensionKey));
  next.missingCriticalInformation = next.useCases.length ? [] : ['Primary use case'];
  normalizeWeights(next);
  return next;
}

function normalizeWeights(intent: UserIntent) {
  const weights = intent.softPreferences;
  const total = Object.values(weights).reduce((sum, value) => sum + value, 0) || 1;
  for (const key of Object.keys(weights) as Array<keyof typeof weights>) weights[key] = Number((weights[key] / total).toFixed(3));
}

function extractBudget(text: string) {
  const normalized = text.toLowerCase();
  const contextual = normalized.match(/(?:预算|最多|不超过|以内|以下|under|below|less than|no more than|budget|[$¥￥])\s*[$¥￥]?\s*(\d+(?:\.\d+)?)/);
  if (contextual) return Number(contextual[1]);
  const bareLimit = normalized.match(/(\d+(?:\.\d+)?)\s*(?:以内|以下|内)/);
  if (bareLimit) return Number(bareLimit[1]);
  const trailing = normalized.match(/[$¥￥]?\s*(\d+(?:\.\d+)?)\s*(?:元|块|rmb|人民币|美元|usd|dollars?|刀)\s*(?:以内|以下|内|or less)?/);
  if (trailing) return Number(trailing[1]);
  return null;
}

function inferCategory(text: string) {
  const normalized = text.toLowerCase();
  if (/sound ?bars?/.test(normalized)) return 'soundbar';
  if (/receivers?|av receiver/.test(normalized)) return 'receiver';
  if (/amplifiers?/.test(normalized)) return 'amplifier';
  if (/home theaters?|surround/.test(normalized)) return 'home theater';
  if (/speakers?/.test(normalized)) return 'speaker';
  if (/earbuds?|headphones?|headset/.test(normalized)) return 'headphones';
  if (/笔|钢笔|圆珠笔|中性笔|pens?\b/.test(normalized)) return 'Office Products';
  if (/名片|business cards?/.test(normalized)) return 'Office Products';
  if (/手机壳|case\b|charger|充电器|线缆|cable/.test(normalized)) return 'Electronics';
  return '';
}

function extractProductQuery(text: string) {
  const normalized = text.trim();
  const english = normalized.match(/(?:find me|looking for|searching for|need|want)\s+(?:a|an|the|some|set of)?\s*([^.,;，。]+)/i);
  if (english?.[1]) return cleanProductQuery(english[1]);
  const chinese = normalized.match(/(?:买|找|推荐|想要|需要)([^，。,.;]+)/);
  if (chinese?.[1]) return cleanProductQuery(chinese[1]);
  return cleanProductQuery(normalized);
}

function cleanProductQuery(value: string) {
  return value
    .replace(/\d+(?:\.\d+)?\s*(元|块|美元|usd|dollars?|以内|以下|预算|items?|stars?)/gi, ' ')
    .replace(/(预算|以内|以下|地铁|通勤|小耳|安卓|android|ios|苹果|舒适|舒服|降噪|性价比|便宜|quality|reviews?|rating|durable|compatible|with reviews mentioning.*)$/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 80);
}

function extractBrandOrStore(text: string) {
  const byBrand = text.match(/\bby\s+([A-Z][A-Za-z0-9&.\- ]{1,40})(?:\s+that|\s+with|,|\.|$)/);
  if (byBrand?.[1]) return byBrand[1].trim();
  const chinese = text.match(/(?:品牌|店铺|店家|商家)[：:\s]*([\w\u4e00-\u9fa5 .&-]{2,30})/);
  return chinese?.[1]?.trim() ?? '';
}

function extractRequiredAttributes(text: string) {
  const out: Array<{ field: string; value: string; source: 'query' }> = [];
  const itemCount = text.match(/(?:exactly|正好|刚好)\s*(\d+)\s*(?:items?|个|支|件|pack)/i);
  if (itemCount?.[1]) out.push({ field: 'Number of Items', value: itemCount[1], source: 'query' });
  const material = text.match(/(?:made from|made of|材质|材料)[^\w\u4e00-\u9fa5]*([A-Za-z\u4e00-\u9fa5 ]{3,60})(?:[,.，。]|$)/i);
  if (material?.[1]) out.push({ field: 'Material', value: material[1].trim(), source: 'query' });
  const size = text.match(/(?:measures?|尺寸|大小|size)[^\w]*(\d+(?:[.\-x×/ ]+\d+)+(?:\s*inches?|\s*inch|厘米|cm)?)/i);
  if (size?.[1]) out.push({ field: 'Size', value: size[1].trim(), source: 'query' });
  return out;
}

function extractReviewEvidenceNeeds(text: string) {
  const out: string[] = [];
  const reviewPhrase = text.match(/reviews?\s+(?:that\s+)?(?:mention|mentioning|say|saying)\s+(.+?)(?:\.|, finally| additionally|$)/i);
  if (reviewPhrase?.[1]) out.push(...reviewPhrase[1].split(/\s+and\s+|[,;，；]/).map((item) => item.trim()));
  const chinese = text.match(/(?:评论|评价|口碑).*(?:提到|说|反馈)([^。；;]+)/);
  if (chinese?.[1]) out.push(...chinese[1].split(/[，、和]/).map((item) => item.trim()));
  return out.filter((item) => item.length > 1).slice(0, 6);
}

function mergeRequiredAttributes(
  existing: Array<{ field: string; value: string; source: 'query' | 'profile' | 'clarification' }>,
  incoming: Array<{ field: string; value: string; source: 'query' }>,
) {
  return unique([...existing, ...incoming], (item) => `${item.field.toLowerCase()}=${item.value.toLowerCase()}`);
}

function canonicalDimensionKey(key: string) {
  return ({
    noise_cancellation: 'noiseCancellation',
    call_quality: 'callQuality',
    price_value: 'priceValue',
    compatibility: 'codecCompatibility',
    review_confidence: 'reviewConfidence',
    water_resistance: 'waterResistance',
  } as Record<string, string>)[key] ?? key;
}

function unique<T>(values: T[], keyFn: (value: T) => string = (value) => String(value)) {
  const seen = new Set<string>();
  const out: T[] = [];
  for (const value of values) {
    const key = keyFn(value);
    if (!seen.has(key)) {
      seen.add(key);
      out.push(value);
    }
  }
  return out;
}
