import { conversationDisplayTitle, demoChatMeta } from './demo';
import type { CartItem, ShoppingMemory } from './shoppingTurn';
import { humanizeText } from './presentation';

export type TasteInsight = {
  id: string;
  title: string;
  understanding: string;
  source: string;
  effect: string;
  conversationId?: string;
  conversationLabel?: string;
  inferred: boolean;
  phrase: string;
};

export function partitionTasteMemories(memories: ShoppingMemory[]) {
  const visible = memories
    .filter((item) => item.enabled && item.status !== 'dismissed' && item.status !== 'superseded')
    .filter((item) => ['personal', 'global', 'long_term'].includes(item.scope || 'personal'))
    .sort((left, right) => (right.priority ?? 50) - (left.priority ?? 50));
  const unique = (items: ShoppingMemory[]) => items.filter((item, index, all) => {
    const label = `${item.normalizedPreference || item.label}`.trim().toLowerCase();
    return all.findIndex((candidate) => `${candidate.normalizedPreference || candidate.label}`.trim().toLowerCase() === label) === index;
  });
  return {
    confirmed: unique(visible.filter((item) => item.userConfirmed || item.sourceType === 'explicit' || item.source === 'explicit')),
    pending: unique(visible.filter((item) => item.status === 'suggested' && !item.userConfirmed)),
  };
}

export function preferenceDisplayLabel(memory: Pick<ShoppingMemory, 'facet' | 'value' | 'label' | 'normalizedPreference'>) {
  return englishPreference(memory.normalizedPreference || memory.label || memory.value, memory.facet);
}

function englishPreference(value: string, facet = '') {
  const raw = `${value || ''}`.trim();
  if (!/[\u3400-\u9fff]/u.test(raw)) return humanizeText(raw);
  if (/兼容|适配/.test(raw) && /最低价格|便宜|价格/.test(raw)) {
    return 'Compatibility matters more than the lowest price for future cable purchases';
  }
  if (/兼容|适配/.test(raw) || facet === 'compatibility') return 'Compatibility first';
  if (/可靠|稳定|耐用/.test(raw) || facet === 'reliability') return 'Reliability matters';
  if (/不用|不需要|多余/.test(raw) && /功能|特性/.test(raw)) return 'Avoid unused features';
  if (/比较|对比/.test(raw) || facet === 'comparison') return 'Compare before buying';
  if (/画质|图像质量/.test(raw) || facet === 'quality') return 'Image quality over price';
  if (/品牌/.test(raw) || facet === 'brand') return "Brand isn't a priority";
  if (/性价比|价格|便宜/.test(raw) || facet === 'value') return 'Good value';
  return 'Saved shopping preference';
}

const UNDERSTANDING: Record<string, string> = {
  compatibility: 'Finding something that works with your setup matters more than saving a little.',
  value: 'Getting solid value matters more to you than paying for a familiar name.',
  brand: 'Brand is a soft signal for you, not the reason to choose.',
  style: 'You lean toward a cleaner, simpler look when products are otherwise close.',
  quality: 'You would rather keep image quality than shave a little off the price.',
  reliability: 'A stable, dependable product matters more to you than an impressive claim on paper.',
};

const EFFECT: Record<string, string> = {
  compatibility: 'Picki checks compatibility before comparing prices.',
  value: 'Picki weighs catalog price more heavily once a product fits the job.',
  brand: 'Picki will not treat a brand name as a hard requirement.',
  style: 'Picki keeps simpler designs in view when they still meet the spec.',
  quality: 'Picki keeps listed picture quality ahead of a small saving.',
  reliability: 'Picki gives verified reliability evidence more weight than unproven feature claims.',
};

export function tasteInsight(memory: ShoppingMemory, conversations: Array<{ id: string; title: string }> = []): TasteInsight {
  const facet = (memory.facet || '').toLowerCase();
  const conversationId = memory.conversationIds?.[0];
  const chat = conversations.find((item) => item.id === conversationId);
  const demo = conversationId ? demoChatMeta(conversationId) : undefined;
  const inferred = memory.sourceType === 'inferred' && !memory.userConfirmed;
  const source = inferred
    ? 'Picki noticed this in your conversations.'
    : demo?.title
      ? `Learned from your ${demo.title.toLowerCase()} conversation`
      : chat?.title
        ? `Learned from ${conversationDisplayTitle(chat)}`
        : memory.evidenceSnippets?.[0]
          ? 'Learned from a conversation with Picki'
          : 'You told Picki this directly.';
  return {
    id: memory.id,
    title: preferenceDisplayLabel(memory),
    understanding: UNDERSTANDING[facet] || 'Picki will keep this in mind when two products both fit.',
    source,
    effect: EFFECT[facet] || 'This preference can change how close options are ranked.',
    conversationId,
    conversationLabel: demo?.title || (chat ? conversationDisplayTitle(chat) : undefined),
    inferred,
    phrase: englishPreference(memory.originalUserExpression || memory.evidence || memory.label, memory.facet),
  };
}

export function picksSummary(cart: CartItem[], memories: ShoppingMemory[], memoryEnabled: boolean): string {
  if (!cart.length) return 'Nothing here yet. Explore a product, or tell Picki what you need.';
  const count = cart.length === 1 ? 'One product you\'re considering.' : `${word(cart.length)} products you're considering.`;
  if (!memoryEnabled) return count;
  const compat = memories.some((item) => item.enabled && (item.facet === 'compatibility' || /compatib/i.test(item.label)));
  const value = memories.some((item) => item.enabled && (item.facet === 'value' || /value|price/i.test(item.label)));
  if (compat) return `${count} Compatibility comes first. Picki keeps that in mind.`;
  if (value) return `${count} Value is in play when two options both fit.`;
  if (memories.some((item) => item.enabled)) return `${count} Picki is using what you have already shared.`;
  return count;
}

function word(count: number) {
  return ['Zero', 'One', 'Two', 'Three', 'Four', 'Five'][count] || String(count);
}
