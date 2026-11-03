import { displayPrice, productTitle } from './format';
import { productTypeHint, unknownChecks, verifiedFacts } from './quickTake';
import type { ProposedShoppingAction, RelatedChat, StructuredPickiResponse, TasteSavedEvent } from './shoppingTurn';
import type { Product, RecommendationResult } from '../types';

export type PickiChatMessage = {
  id: string;
  from: 'you' | 'picki';
  text: string;
  product?: Product;
  products?: Product[];
  why?: string;
  check?: string;
  structured?: StructuredPickiResponse | null;
  proposedActions?: ProposedShoppingAction[];
  tasteSaved?: TasteSavedEvent;
};

export function chatId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

export function conversationTitle(messages: PickiChatMessage[], fallback = '新对话') {
  const first = messages.find((item) => item.from === 'you');
  const text = (first?.text || fallback).replace(/\s+/g, ' ').trim();
  return text.length > 42 ? `${text.slice(0, 39)}…` : text;
}

export function youMessage(text: string): PickiChatMessage {
  return { id: chatId('you'), from: 'you', text };
}

export function pickiMessage(text: string, extras: Partial<PickiChatMessage> = {}): PickiChatMessage {
  return { id: chatId('picki'), from: 'picki', text, ...extras };
}

export function productIdsInMessages(messages: PickiChatMessage[]): string[] {
  const ids: string[] = [];
  for (const message of messages) {
    if (message.product?.id) ids.push(message.product.id);
    for (const product of message.products ?? []) if (product.id) ids.push(product.id);
    for (const ref of message.structured?.productRefs ?? []) if (ref.productId) ids.push(ref.productId);
    for (const column of message.structured?.comparisonData?.columns ?? []) if (column.productId) ids.push(column.productId);
  }
  return [...new Set(ids)];
}

export function newestSharedConversation(groups: RelatedChat[][]): RelatedChat | null {
  if (!groups.length || groups.some((group) => !group.length)) return null;
  const remainingIds = groups.slice(1).map((group) => new Set(group.map((chat) => chat.id)));
  return groups[0]
    .filter((chat) => remainingIds.every((ids) => ids.has(chat.id)))
    .sort((left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime())[0] ?? null;
}

export function isCableShoppingConversation(messages: PickiChatMessage[]): boolean {
  return messages.some((message) => {
    const text = [
      message.text,
      message.structured?.primaryMessage,
      ...(message.structured?.productRefs ?? []).flatMap((ref) => [ref.productId, ref.title, ref.specLine]),
      ...(message.structured?.comparisonData?.columns ?? []).map((column) => column.productId),
    ].filter(Boolean).join(' ').toLowerCase();
    return /\b(hdmi|dvi|cable|connector)\b/.test(text);
  });
}

export function messageShowsGuidedActions(messageId: string, latestPickiId?: string) {
  return Boolean(latestPickiId && messageId === latestPickiId);
}

export function replyFromFind(result: RecommendationResult, request: string): PickiChatMessage {
  const primary = result.primaryRecommendation;
  if (!primary) {
    const excluded = result.excludedProducts[0]?.reason;
    return pickiMessage(excluded
      ? `I searched the live catalog, but nothing passed the hard filters yet. ${excluded} You can loosen the request and I’ll look again.`
      : `I couldn’t find a confident match for “${request}” in the current Home Audio catalog. Tell me a product type, budget, or room and I’ll try again.`);
  }
  const why = primary.reasons[0] || result.evidenceSummary;
  const check = primary.regretGuard || result.regretGuard || result.missingInformation[0];
  const type = productTypeHint(primary.product);
  const intro = result.parsedIntent.category && result.parsedIntent.category !== 'any'
    ? `I treated this as a ${result.parsedIntent.category} search.`
    : `Here’s the strongest match I can support with catalog facts.`;
  return pickiMessage(`${intro} My pick is ${productTitle(primary.product)} at ${displayPrice(primary.product)}.${why ? ` ${why}` : ''}`, {
    product: primary.product,
    why,
    check: check ? String(check) : undefined,
  });
}

export function replyFromProduct(product: Product, result: RecommendationResult | null, need: string): PickiChatMessage {
  const facts = verifiedFacts(product);
  const type = productTypeHint(product);
  const checks = unknownChecks(product, need, result);
  const why = result?.primaryRecommendation?.reasons[0] || result?.evidenceSummary;
  const lines = [
    `This listing looks like a ${type}.`,
    facts.slice(0, 3).join(' · '),
  ];
  if (need.trim() && why) lines.push(why);
  else if (!need.trim()) lines.push('Tell me how you plan to use it, and I’ll help you decide.');
  if (checks[0]) lines.push(`Worth checking: ${checks[0]}`);
  return pickiMessage(lines.filter(Boolean).join(' '), {
    product,
    why: need.trim() ? why : undefined,
    check: checks[0],
  });
}
