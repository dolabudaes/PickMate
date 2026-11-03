import type { PickiChatMessage } from './pickiTalk';
import { humanizeText } from './presentation';

export function rememberConversationScroll(
  positions: Record<string, number>,
  conversationId: string | null,
  offset: number,
): Record<string, number> {
  if (!conversationId) return positions;
  return { ...positions, [conversationId]: Math.max(0, offset) };
}

export function conversationScrollOffset(positions: Record<string, number>, conversationId: string | null): number {
  if (!conversationId) return 0;
  return Math.max(0, positions[conversationId] ?? 0);
}

export function conversationInitialScrollTarget(messageCount: number): 'top' | 'end' {
  return messageCount > 0 ? 'end' : 'top';
}

const SNAKE_KEY = /_([a-z])/g;

function camelKey(key: string) {
  return key.replace(SNAKE_KEY, (_, letter: string) => letter.toUpperCase());
}

function normalizeStructuredValue(value: unknown): unknown {
  if (typeof value === 'string') return humanizeText(value);
  if (Array.isArray(value)) return value.map(normalizeStructuredValue);
  if (!value || typeof value !== 'object') return value;
  const output: Record<string, unknown> = {};
  for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
    output[camelKey(key)] = normalizeStructuredValue(child);
  }
  return output;
}

export function mapPersistedConversationState(state: Record<string, unknown>): Record<string, unknown> {
  const messages = Array.isArray(state.messages)
    ? state.messages.map((item) => {
      if (!item || typeof item !== 'object') return item;
      const message = item as Record<string, unknown>;
      return {
        ...message,
        structured: normalizeStructuredValue(message.structured),
        tasteSaved: normalizeStructuredValue(message.tasteSaved),
        proposedActions: normalizeStructuredValue(message.proposedActions),
      };
    })
    : state.messages;
  return { ...state, messages };
}

export function asPickiMessages(state: Record<string, unknown>): PickiChatMessage[] {
  const normalized = mapPersistedConversationState(state);
  return Array.isArray(normalized.messages) ? normalized.messages as PickiChatMessage[] : [];
}
