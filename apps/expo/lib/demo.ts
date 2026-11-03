export function resolveDemoMode(...values: Array<string | undefined>) {
  const explicit = values.map((value) => `${value ?? ''}`.trim().toLowerCase()).filter(Boolean);
  if (explicit.includes('false') || explicit.includes('0') || explicit.includes('no')) return false;
  return true;
}

export const DEMO_MODE = resolveDemoMode(process.env.EXPO_PUBLIC_DEMO_MODE, process.env.PICKMATE_DEMO_MODE);
export const DEMO_SESSION_ID = process.env.EXPO_PUBLIC_DEMO_SESSION_ID || 'pickmate-launch-demo';
export const DEMO_DATA_VERSION = '2026-10-29-coherent-two-product-v3';
const DEMO_ACTIVE_CONVERSATION_KEY = 'pickmate_demo_active_conversation';

export const DEMO_CHATS: Record<string, { title: string; subtitle: string }> = {
  'demo-old-monitor-future-upgrade': { title: 'Old Monitor, Future Upgrade', subtitle: 'HDMI-to-DVI now · 4K 120Hz later' },
  'demo-best-value-4k-tv': { title: 'Best Value for My 4K TV', subtitle: '4K 60Hz · useful value' },
};

export function demoChatMeta(id: string) {
  return DEMO_CHATS[id];
}

export function conversationDisplayTitle(conversation: { id: string; title?: string | null }): string {
  const featuredTitle = demoChatMeta(conversation.id)?.title;
  if (featuredTitle) return featuredTitle;

  const title = `${conversation.title || ''}`.trim();
  if (!title) return 'Untitled conversation';
  if (!/[\u3400-\u9fff]/u.test(title)) return title;
  if (/^(新对话|新的对话|新聊天)$/.test(title)) return 'New conversation';
  if (/^请?分析\s*/.test(title)) {
    const product = title.replace(/^请?分析\s*/, '').trim();
    return product && !/[\u3400-\u9fff]/u.test(product) ? `Analyze ${product}` : 'Product analysis';
  }
  if (/旧显示器|DVI.*HDMI|HDMI.*DVI/i.test(title)) return 'Old Monitor, Future Upgrade';
  return 'Shopping conversation';
}

const FEATURED_DEMO_CHAT_IDS = [
  'demo-old-monitor-future-upgrade',
  'demo-best-value-4k-tv',
] as const;

export function preferredDemoConversationId<T extends { id: string }>(items: T[], currentSessionId: string | null = null): string | null {
  if (currentSessionId && items.some((item) => item.id === currentSessionId)) return currentSessionId;
  if (items.some((item) => item.id === FEATURED_DEMO_CHAT_IDS[0])) return FEATURED_DEMO_CHAT_IDS[0];
  return items[0]?.id ?? null;
}

export function readDemoConversationSelection(): string | null {
  if (typeof sessionStorage === 'undefined') return null;
  try {
    return sessionStorage.getItem(DEMO_ACTIVE_CONVERSATION_KEY);
  } catch {
    return null;
  }
}

export function rememberDemoConversationSelection(id: string | null) {
  if (typeof sessionStorage === 'undefined') return;
  try {
    if (id) sessionStorage.setItem(DEMO_ACTIVE_CONVERSATION_KEY, id);
    else sessionStorage.removeItem(DEMO_ACTIVE_CONVERSATION_KEY);
  } catch {
    // Selection persistence is optional; keep the active conversation usable
    // when a browser's privacy policy blocks session storage.
  }
}

export function orderDemoConversations<T extends { id: string; updatedAt: string }>(items: T[]): T[] {
  return [...items].sort((left, right) => {
    const leftIndex = FEATURED_DEMO_CHAT_IDS.indexOf(left.id as (typeof FEATURED_DEMO_CHAT_IDS)[number]);
    const rightIndex = FEATURED_DEMO_CHAT_IDS.indexOf(right.id as (typeof FEATURED_DEMO_CHAT_IDS)[number]);
    if (leftIndex >= 0 || rightIndex >= 0) {
      return (leftIndex < 0 ? FEATURED_DEMO_CHAT_IDS.length : leftIndex)
        - (rightIndex < 0 ? FEATURED_DEMO_CHAT_IDS.length : rightIndex);
    }
    return new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime();
  });
}
