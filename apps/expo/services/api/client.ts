import Constants from 'expo-constants';
import { Platform } from 'react-native';
import type { CartItem, ComparisonRecord, LivePickCard, MemoryEvent, PickAction, PickiClarificationOption, PickiComparisonData, PickiDetailSection, PickiProductRef, PickTurnResult, ProposedShoppingAction, RelatedChat, SavedPick, ShoppingMemory, StructuredPickiResponse, SuggestedPickiAction } from '../../lib/shoppingTurn';
import type { Product, RecommendationEvidence, RecommendationProduct, RecommendationResult, SavedDecision, UserIntent } from '../../types';
import { DEMO_MODE, DEMO_SESSION_ID } from '../../lib/demo';
import { parseIntent } from '../../lib/intent';
import { humanizeProduct } from '../../lib/presentation';
import { mapPersistedConversationState } from '../../lib/conversationHistory';

export const API_BASE_URL = resolveApiBaseUrl();

function resolveApiBaseUrl() {
  const configured = process.env.EXPO_PUBLIC_API_URL || 'http://127.0.0.1:8011';
  const lanHost = lanHostFromExpo();
  if (lanHost && /127\.0\.0\.1|localhost/.test(configured)) {
    return configured.replace(/127\.0\.0\.1|localhost/, lanHost);
  }
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    const host = window.location.hostname;
    if (host && host !== 'localhost' && host !== '127.0.0.1') {
      return `http://${host}:8011`;
    }
  }
  return configured;
}

function lanHostFromExpo() {
  const constants = Constants as Record<string, any>;
  const candidates = [
    constants.expoGoConfig?.debuggerHost,
    constants.expoConfig?.hostUri,
    constants.manifest?.debuggerHost,
    constants.manifest2?.extra?.expoClient?.hostUri,
  ];
  for (const candidate of candidates) {
    if (!candidate) continue;
    const host = String(candidate).split(':')[0];
    if (host && host !== 'localhost' && host !== '127.0.0.1') return host;
  }
  return null;
}
const SESSION_KEY = 'pickmate_session_id';

type StorageLike = {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
};

export class PickMateApiClient {
  constructor(private readonly storage: StorageLike, private readonly baseUrl = API_BASE_URL) {}

  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers);
    if (options.body != null && !headers.has('content-type')) headers.set('content-type', 'application/json');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 45000);
    try {
      const response = await fetch(`${this.baseUrl}${path}`, { ...options, headers, signal: controller.signal });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `PickMate request failed (${response.status})`);
      return data as T;
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') throw new Error('The request timed out. Please try again.');
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }

  async sessionId() {
    if (DEMO_MODE) {
      await this.storage.setItem(SESSION_KEY, DEMO_SESSION_ID);
      return DEMO_SESSION_ID;
    }
    const existing = await this.storage.getItem(SESSION_KEY);
    if (existing && existing !== DEMO_SESSION_ID) return existing;
    const created = await this.request<{ session_id: string }>('/sessions', { method: 'POST' });
    await this.storage.setItem(SESSION_KEY, created.session_id);
    return created.session_id;
  }

  async demoStatus() {
    return this.request<{ demo_version: string; session_id: string; conversations: Array<{ id: string; title: string }>; cart_ids: string[] }>('/demo/status');
  }

  async resetDemo() {
    return this.request<Record<string, unknown>>('/demo/reset', { method: 'POST' });
  }

  async catalog() {
    return this.request<{
      catalog: string;
      product_count: number;
      priced_count?: number;
      currency?: string;
      categories: string[];
      brands?: string[];
      product_types?: string[];
      schema: string;
    }>('/catalog');
  }

  async products(params: { q?: string; brand?: string; maxPrice?: number | null; sort?: string; limit?: number; offset?: number } = {}) {
    const query = new URLSearchParams();
    if (params.q) query.set('q', params.q);
    if (params.brand && params.brand !== 'All') query.set('brand', params.brand);
    if (params.maxPrice != null) query.set('max_price', String(params.maxPrice));
    if (params.sort) query.set('sort', params.sort);
    query.set('limit', String(params.limit ?? 24));
    query.set('offset', String(params.offset ?? 0));
    return this.request<{ items: Product[]; count: number; limit: number; offset: number }>(`/products?${query.toString()}`);
  }

  async decisionState() {
    const session_id = await this.sessionId();
    return this.request<{ state: Record<string, unknown> }>(`/sessions/${session_id}/decision-state`);
  }

  async saveDecisionState(state: Record<string, unknown>) {
    const session_id = await this.sessionId();
    return this.request(`/sessions/${session_id}/decision-state`, { method: 'PUT', body: JSON.stringify(state) });
  }

  async listConversations() {
    const session_id = await this.sessionId();
    return this.request<Array<{ id: string; title: string; createdAt: string; updatedAt: string; manualTitle?: boolean }>>(`/sessions/${session_id}/conversations`);
  }

  async createConversation(input: { title?: string; state?: Record<string, unknown> } = {}) {
    const session_id = await this.sessionId();
    const row = await this.request<{ id: string; title: string; createdAt: string; updatedAt: string; state: Record<string, unknown> }>(`/sessions/${session_id}/conversations`, {
      method: 'POST',
      body: JSON.stringify({ title: input.title ?? 'New conversation', state: input.state ?? {} }),
    });
    return { ...row, state: mapPersistedConversationState(row.state || {}) };
  }

  async renameConversation(id: string, title: string) {
    const session_id = await this.sessionId();
    return this.request<{ id: string; title: string; createdAt: string; updatedAt: string; state?: Record<string, unknown> }>(`/sessions/${session_id}/conversations/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    });
  }

  async deleteConversation(id: string) {
    const session_id = await this.sessionId();
    return this.request<{ deleted: boolean; id: string }>(`/sessions/${session_id}/conversations/${id}`, { method: 'DELETE' });
  }

  async getConversation(id: string) {
    const session_id = await this.sessionId();
    const row = await this.request<{ id: string; title: string; createdAt: string; updatedAt: string; state: Record<string, unknown> }>(`/sessions/${session_id}/conversations/${id}`);
    return { ...row, state: mapPersistedConversationState(row.state || {}) };
  }

  async saveConversation(id: string, title: string, state: Record<string, unknown>) {
    const session_id = await this.sessionId();
    return this.request(`/sessions/${session_id}/conversations/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ title, state }),
    });
  }

  async product(id: string) {
    return this.request<Product>(`/products/${id}`);
  }

  async event(name: string, productId?: string) {
    const session_id = await this.sessionId();
    return this.request('/events', { method: 'POST', body: JSON.stringify({ session_id, name, product_id: productId }) });
  }

  async pickiTurn(input: { conversationId: string; message?: string; action?: PickAction; productId?: string }) {
    const session_id = await this.sessionId();
    const response = await this.request<Record<string, unknown>>('/picki/turn', {
      method: 'POST',
      body: JSON.stringify({
        session_id,
        conversation_id: input.conversationId,
        message: input.message ?? '',
        action: input.action ?? 'message',
        product_id: input.productId,
      }),
    });
    return mapTurn(response);
  }

  async executeAgentAction(input: { conversationId?: string; type: 'cart_update' | 'preference_update'; payload: Record<string, unknown> }) {
    const session_id = await this.sessionId();
    return this.request<{ status: string; results?: unknown[]; reason?: string }>('/picki/actions/execute', {
      method: 'POST',
      body: JSON.stringify({
        session_id,
        conversation_id: input.conversationId ?? null,
        type: input.type,
        payload: input.payload,
      }),
    });
  }

  async shoppingMemories() {
    const session_id = await this.sessionId();
    const response = await this.request<{ memory_enabled: boolean; items: Array<Record<string, unknown>> }>(`/shopping/memories?session_id=${encodeURIComponent(session_id)}`);
    return {
      memoryEnabled: response.memory_enabled !== false,
      items: (response.items ?? []).map(mapMemory),
    };
  }

  async forgetMemory(id: string) {
    const session_id = await this.sessionId();
    return this.request(`/shopping/memories/${encodeURIComponent(id)}?session_id=${encodeURIComponent(session_id)}`, { method: 'DELETE' });
  }

  async patchMyTaste(id: string, patch: { label?: string; normalizedPreference?: string; status?: string; userConfirmed?: boolean; priority?: number }) {
    const session_id = await this.sessionId();
    return this.request(`/my-taste/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({
        session_id,
        label: patch.label,
        normalized_preference: patch.normalizedPreference ?? patch.label,
        status: patch.status,
        user_confirmed: patch.userConfirmed,
        priority: patch.priority,
      }),
    });
  }

  async setShoppingMemory(enabled: boolean) {
    const session_id = await this.sessionId();
    return this.request('/shopping/memory', { method: 'PUT', body: JSON.stringify({ session_id, enabled }) });
  }

  async savedPicks() {
    const session_id = await this.sessionId();
    const rows = await this.request<Array<Record<string, unknown>>>(`/shopping/saves?session_id=${encodeURIComponent(session_id)}`);
    return rows.map(mapSavedPick);
  }

  async savePick(productId: string, conversationId: string | null, reason: string) {
    const session_id = await this.sessionId();
    return this.request('/shopping/saves', {
      method: 'POST',
      body: JSON.stringify({ session_id, conversation_id: conversationId, product_id: productId, reason }),
    });
  }

  async cart() {
    const session_id = await this.sessionId();
    const rows = await this.request<Array<Record<string, unknown>>>(`/shopping/cart?session_id=${encodeURIComponent(session_id)}`);
    return rows.map(mapCartItem);
  }

  async addCartItem(productId: string, conversationId: string | null, sourceType: 'chat' | 'product') {
    const session_id = await this.sessionId();
    return this.request('/shopping/cart', {
      method: 'POST',
      body: JSON.stringify({ session_id, product_id: productId, conversation_id: conversationId, source_type: sourceType }),
    });
  }

  async removeCartItem(productId: string) {
    const session_id = await this.sessionId();
    return this.request(`/shopping/cart/${encodeURIComponent(productId)}?session_id=${encodeURIComponent(session_id)}`, { method: 'DELETE' });
  }

  async addTaste(label: string) {
    const session_id = await this.sessionId();
    return this.request('/shopping/memories', { method: 'POST', body: JSON.stringify({ session_id, label }) });
  }

  async comparisons() {
    const session_id = await this.sessionId();
    const rows = await this.request<Array<Record<string, unknown>>>(`/shopping/comparisons?session_id=${encodeURIComponent(session_id)}`);
    return rows.map(mapComparison);
  }

  async createComparison(productIds: string[]) {
    const session_id = await this.sessionId();
    const row = await this.request<Record<string, unknown>>('/shopping/comparisons', {
      method: 'POST',
      body: JSON.stringify({ session_id, product_ids: productIds }),
    });
    return mapComparison(row);
  }

  async linkComparison(comparisonId: string, conversationId: string) {
    const session_id = await this.sessionId();
    const row = await this.request<Record<string, unknown>>(`/shopping/comparisons/${encodeURIComponent(comparisonId)}/conversation`, {
      method: 'POST',
      body: JSON.stringify({ session_id, conversation_id: conversationId }),
    });
    return mapComparison(row);
  }

  async productConversations(productId: string) {
    const session_id = await this.sessionId();
    const rows = await this.request<Array<Record<string, unknown>>>(`/shopping/products/${encodeURIComponent(productId)}/conversations?session_id=${encodeURIComponent(session_id)}`);
    return rows.map((row): RelatedChat => ({
      id: String(row.id),
      title: String(row.title ?? 'Conversation'),
      updatedAt: String(row.updated_at ?? ''),
    }));
  }

  async relatedConversations(productIds: string[]) {
    const session_id = await this.sessionId();
    const query = new URLSearchParams({ session_id });
    for (const productId of [...new Set(productIds.filter(Boolean))]) query.append('product_ids', productId);
    if (!query.getAll('product_ids').length) return [];
    const rows = await this.request<Array<Record<string, unknown>>>(`/shopping/related-conversations?${query.toString()}`);
    return rows.map((row): RelatedChat => ({
      id: String(row.id),
      title: String(row.title ?? 'Conversation'),
      updatedAt: String(row.updated_at ?? ''),
      relatedProductCount: Number(row.related_product_count ?? 0),
    }));
  }

  async removeSavedPick(productId: string) {
    const session_id = await this.sessionId();
    return this.request(`/shopping/saves/${encodeURIComponent(productId)}?session_id=${encodeURIComponent(session_id)}`, { method: 'DELETE' });
  }

  async recommend(message: string, candidateIds: string[] = [], currentProductId?: string, endpoint: 'recommend' | 'update' | 'compare' | 'decide' | 'price-check' | 'product-question' = 'recommend') {
    const session_id = await this.sessionId();
    const response = await this.request<HarnessResponse>(`/picki/${endpoint}`, {
      method: 'POST',
      body: JSON.stringify({ session_id, message, current_product_id: currentProductId, candidate_product_ids: candidateIds }),
    });
    return harnessToRecommendation(response, message);
  }

  async saveDecision(userNeed: string, result: RecommendationResult) {
    const session_id = await this.sessionId();
    return this.request<SavedDecision>('/decisions', { method: 'POST', body: JSON.stringify({ session_id, user_need: userNeed, result }) });
  }

  async savedDecisions() {
    const session_id = await this.sessionId();
    return this.request<SavedDecision[]>(`/sessions/${session_id}/decisions`);
  }

  async profile() {
    const session_id = await this.sessionId();
    return this.request(`/profile?session_id=${encodeURIComponent(session_id)}`);
  }

  async savePreference(
    preference: string,
    options: {
      weight?: number;
      value?: unknown;
      source?: 'explicit' | 'confirmed' | 'decision_history' | 'behavior_inferred';
      scope?: 'session' | 'long_term' | 'category' | 'observed';
    } = {},
  ) {
    const session_id = await this.sessionId();
    const source = options.source ?? 'explicit';
    return this.request('/profile/preferences', {
      method: 'POST',
      body: JSON.stringify({
        session_id,
        preference,
        weight: options.weight,
        value: options.value ?? options.weight,
        source,
        scope: options.scope ?? 'long_term',
        confidence: source === 'behavior_inferred' ? 0.62 : 0.92,
      }),
    });
  }

  async deletePreference(preference: string) {
    const session_id = await this.sessionId();
    return this.request(`/profile/preferences/${encodeURIComponent(preference)}?session_id=${encodeURIComponent(session_id)}`, { method: 'DELETE' });
  }
}

type HarnessResponse = {
  run_id: string;
  intent: Record<string, any>;
  primary: RecommendationProduct | null;
  alternatives: RecommendationProduct[];
  regret_guard: string | { most_likely_regret: string; why_it_matters: string; switch_condition: string };
  evidence_summary: string;
  missing_information: string[];
  data_updated_at: string;
  used_preferences?: string[];
  switch_conditions?: Array<{ condition: string; new_primary: Product; reason: string }>;
  fallback_used?: boolean;
  trace_id?: string;
  excluded_products: Array<{ product: Product; reason: string }>;
};

export function harnessToRecommendation(response: HarnessResponse, rawText: string): RecommendationResult {
  const regretText = typeof response.regret_guard === 'string'
    ? response.regret_guard
    : `${response.regret_guard.most_likely_regret}. ${response.regret_guard.switch_condition}`;
  const primary = response.primary ? normalizeRecommendationProduct(response.primary, regretText) : null;
  return {
    id: response.run_id,
    parsedIntent: intentToClient(response.intent, rawText),
    excludedProducts: response.excluded_products ?? [],
    primaryRecommendation: primary,
    alternatives: (response.alternatives ?? []).map((item) => normalizeRecommendationProduct(item, item.regretGuard || regretText)),
    regretGuard: regretText,
    evidenceSummary: response.evidence_summary,
    switchConditions: (response.switch_conditions ?? []).map((item) => ({
      condition: item.condition,
      newPrimary: item.new_primary,
      reason: item.reason,
    })),
    fallbackUsed: response.fallback_used,
    traceId: response.trace_id,
    missingInformation: response.missing_information ?? [],
    dataUpdatedAt: response.data_updated_at,
    usedPreferences: response.used_preferences ?? [],
    trace: {
      profileSignalsUsed: [],
      inferredPreferencesUsed: [],
      confirmedPreferencesUsed: (response.used_preferences ?? []).map((label) => ({
        key: label,
        label,
        source: 'confirmed' as const,
      })),
      profileChangedRanking: Boolean(response.used_preferences?.length),
    },
  };
}

function normalizeRecommendationProduct(item: RecommendationProduct, regretGuard: string): RecommendationProduct {
  return {
    ...item,
    regretGuard,
    evidence: (item.evidence ?? []) as RecommendationEvidence[],
    relevantRisks: item.relevantRisks ?? [],
  };
}

function intentToClient(intent: Record<string, any>, rawText: string): UserIntent {
  const parsed = parseIntent(rawText);
  return {
    ...parsed,
    category: intent.category ?? parsed.category,
    budget: intent.budget ?? parsed.budget,
    hardConstraints: {
      inStock: intent.hard_constraints?.in_stock ?? parsed.hardConstraints.inStock,
      devicePlatform: intent.hard_constraints?.device_platform ?? parsed.hardConstraints.devicePlatform,
      formFactor: intent.hard_constraints?.form_factor ?? parsed.hardConstraints.formFactor,
      brandOrStore: intent.hard_constraints?.brand_or_store ?? parsed.hardConstraints.brandOrStore,
      requiredTerms: intent.hard_constraints?.required_terms ?? parsed.hardConstraints.requiredTerms,
      requiredAttributes: intent.hard_constraints?.required_attributes ?? parsed.hardConstraints.requiredAttributes,
    },
    useCases: intent.use_cases ?? parsed.useCases,
    softPreferences: {
      noiseCancellation: intent.priorities?.noise_cancellation ?? parsed.softPreferences.noiseCancellation,
      comfort: intent.priorities?.comfort ?? parsed.softPreferences.comfort,
      callQuality: intent.priorities?.call_quality ?? parsed.softPreferences.callQuality,
      battery: intent.priorities?.battery ?? parsed.softPreferences.battery,
      priceValue: intent.priorities?.price_value ?? parsed.softPreferences.priceValue,
      codecCompatibility: intent.priorities?.compatibility ?? parsed.softPreferences.codecCompatibility,
      waterResistance: intent.priorities?.water_resistance ?? parsed.softPreferences.waterResistance,
      multipoint: intent.priorities?.multipoint ?? parsed.softPreferences.multipoint,
      quality: intent.priorities?.quality ?? parsed.softPreferences.quality,
      durability: intent.priorities?.durability ?? parsed.softPreferences.durability,
      reviewConfidence: intent.priorities?.review_confidence ?? parsed.softPreferences.reviewConfidence,
    },
    fitNeeds: {
      smallEarFriendly: intent.small_ear_friendly ?? parsed.fitNeeds.smallEarFriendly,
      avoidDeepInsertion: intent.avoid_deep_insertion ?? parsed.fitNeeds.avoidDeepInsertion,
    },
    dealbreakers: intent.dealbreakers ?? parsed.dealbreakers,
    explicitConcerns: intent.explicit_concerns ?? parsed.explicitConcerns,
    missingCriticalInformation: intent.missing_information ?? parsed.missingCriticalInformation,
    productQuery: intent.product_query ?? parsed.productQuery,
    reviewEvidenceNeeds: intent.review_evidence_needs ?? parsed.reviewEvidenceNeeds,
    decisionDimensions: intent.decision_dimensions ?? parsed.decisionDimensions,
    rawText,
  };
}

function mapTurn(response: Record<string, unknown>): PickTurnResult {
  const actions = Array.isArray(response.quick_actions) ? response.quick_actions : [];
  const proposed = Array.isArray(response.proposed_actions) ? response.proposed_actions.map(mapProposedAction) : [];
  return {
    conversationId: String(response.conversation_id ?? ''),
    message: String(response.message ?? ''),
    activePick: mapCard(response.active_pick),
    alternatives: Array.isArray(response.alternatives) ? response.alternatives.map(mapCard).filter((item): item is LivePickCard => Boolean(item)) : [],
    quickActions: actions.filter((item): item is PickTurnResult['quickActions'][number] => item === 'cheaper' || item === 'different_style' || item === 'compare' || item === 'why_this'),
    changedSinceLastPick: Array.isArray(response.changed_since_last_pick) ? response.changed_since_last_pick.map(String) : [],
    memoryEvent: mapMemoryEvent(response.memory_event),
    structuredResponse: mapStructuredResponse(response.structured_response),
    proposedActions: proposed,
    agentTraceId: typeof response.agent_trace_id === 'string' ? response.agent_trace_id : null,
    tasteSaved: mapTasteSaved(response.taste_saved),
  };
}

function mapTasteSaved(value: unknown): PickTurnResult['tasteSaved'] {
  if (!value || typeof value !== 'object') return null;
  const row = value as Record<string, unknown>;
  const label = typeof row.label === 'string' ? row.label : '';
  const id = typeof row.id === 'string' ? row.id : '';
  if (!label || !id) return null;
  const ids = Array.isArray(row.ids) ? row.ids.map(String) : [id];
  const labels = Array.isArray(row.labels) ? row.labels.map(String) : [label];
  return {
    id,
    ids,
    labels,
    label,
    undoable: row.undoable !== false,
    sourceType: row.source_type === 'inferred' ? 'inferred' : 'explicit',
  };
}

function mapStructuredResponse(value: unknown): PickTurnResult['structuredResponse'] {
  if (!value || typeof value !== 'object') return null;
  const row = value as Record<string, unknown>;
  return {
    message: String(row.message ?? row.primary_message ?? ''),
    responseMode: row.response_mode === 'QUICK' || row.response_mode === 'STANDARD' || row.response_mode === 'DEEP'
      ? (row.response_mode as StructuredPickiResponse['responseMode'])
      : null,
    primaryMessage: typeof row.primary_message === 'string' ? row.primary_message : null,
    keyFacts: Array.isArray(row.key_facts)
      ? row.key_facts.filter((item) => item && typeof item === 'object').map((item) => ({ text: String((item as Record<string, unknown>).text ?? '') }))
      : [],
    productRefs: Array.isArray(row.product_refs) ? row.product_refs.map(mapProductRef) : [],
    detailSections: Array.isArray(row.detail_sections) ? row.detail_sections.map(mapDetailSection) : [],
    suggestedActions: Array.isArray(row.suggested_actions) ? row.suggested_actions.map(mapSuggestedAction) : [],
    directRecommendation: typeof row.direct_recommendation === 'string'
      ? row.direct_recommendation
      : typeof (row.product_brief as Record<string, unknown> | undefined)?.direct_recommendation === 'string'
        ? String((row.product_brief as Record<string, unknown>).direct_recommendation)
        : null,
    productHighlights: Array.isArray(row.product_highlights) ? row.product_highlights.map(String) : [],
    technicalSpecifications: Array.isArray(row.technical_specifications) ? row.technical_specifications.map(String) : [],
    priceValueAnalysis: typeof row.price_value_analysis === 'string' ? row.price_value_analysis : null,
    customerReviewSummary: typeof row.customer_review_summary === 'string' ? row.customer_review_summary : null,
    productComparisons: typeof row.product_comparisons === 'string' ? row.product_comparisons : null,
    importantDrawbacks: Array.isArray(row.important_drawbacks) ? row.important_drawbacks.map(String) : [],
    suggestedFollowUpQuestions: Array.isArray(row.suggested_follow_up_questions) ? row.suggested_follow_up_questions.map(String) : [],
    proposedActions: Array.isArray(row.proposed_actions) ? row.proposed_actions.map(mapProposedAction) : [],
    evidenceNotes: Array.isArray(row.evidence_notes) ? row.evidence_notes.map(String) : [],
    responseType: typeof row.response_type === 'string' ? row.response_type : null,
    comparisonData: mapComparisonData(row.comparison_data),
    clarificationOptions: Array.isArray(row.clarification_options) ? row.clarification_options.map(mapClarificationOption) : [],
    decisionHighlight: typeof row.decision_highlight === 'string' ? row.decision_highlight : null,
    evidenceStatus: typeof row.evidence_status === 'string' ? row.evidence_status : null,
    decisionBrief: mapDecisionBrief(row.decision_brief),
  };
}

function mapDecisionBrief(value: unknown): StructuredPickiResponse['decisionBrief'] {
  if (!value || typeof value !== 'object') return null;
  const row = value as Record<string, unknown>;
  const review = row.review && typeof row.review === 'object' ? row.review as Record<string, unknown> : null;
  return {
    angles: Array.isArray(row.angles)
      ? row.angles.filter((item) => item && typeof item === 'object').map((item) => {
        const angle = item as Record<string, unknown>;
        return { id: String(angle.id ?? ''), title: String(angle.title ?? ''), body: String(angle.body ?? '') };
      })
      : [],
    review: review
      ? {
        available: Boolean(review.available),
        lines: Array.isArray(review.lines) ? review.lines.map(String) : [],
        quotes: Array.isArray(review.quotes)
          ? review.quotes.filter((item) => item && typeof item === 'object').map((item) => {
            const quote = item as Record<string, unknown>;
            return { productId: typeof quote.product_id === 'string' ? quote.product_id : undefined, snippet: typeof quote.snippet === 'string' ? quote.snippet : undefined };
          })
          : [],
      }
      : null,
    gap: typeof row.gap === 'string' ? row.gap : null,
    changeCondition: typeof row.change_condition === 'string' ? row.change_condition : null,
    switches: Array.isArray(row.switches)
      ? row.switches.filter((item) => item && typeof item === 'object').map((item) => {
        const option = item as Record<string, unknown>;
        return { id: String(option.id ?? ''), label: String(option.label ?? ''), message: String(option.message ?? option.label ?? '') };
      })
      : [],
    evidence: Array.isArray(row.evidence)
      ? row.evidence.filter((item) => item && typeof item === 'object').map((item) => {
        const ev = item as Record<string, unknown>;
        return {
          source: typeof ev.source === 'string' ? ev.source : undefined,
          productId: typeof ev.product_id === 'string' ? ev.product_id : undefined,
          evidenceType: typeof ev.evidence_type === 'string' ? ev.evidence_type : undefined,
          claim: typeof ev.claim === 'string' ? ev.claim : undefined,
          availability: typeof ev.availability === 'string' ? ev.availability : undefined,
          decisionRelevance: typeof ev.decision_relevance === 'string' ? ev.decision_relevance : undefined,
        };
      })
      : [],
    winnerProductId: typeof row.winner_product_id === 'string' ? row.winner_product_id : null,
  };
}

function mapClarificationOption(value: unknown): PickiClarificationOption {
  const row = (value && typeof value === 'object' ? value : {}) as Record<string, unknown>;
  return {
    id: String(row.id ?? ''),
    label: String(row.label ?? ''),
    message: String(row.message ?? row.label ?? ''),
  };
}

function mapComparisonData(value: unknown): PickiComparisonData | null {
  if (!value || typeof value !== 'object') return null;
  const row = value as Record<string, unknown>;
  return {
    winnerProductId: typeof row.winner_product_id === 'string' ? row.winner_product_id : null,
    columns: Array.isArray(row.columns)
      ? row.columns.filter((item) => item && typeof item === 'object').map((item) => {
        const col = item as Record<string, unknown>;
        return {
          productId: typeof col.product_id === 'string' ? col.product_id : undefined,
          title: typeof col.title === 'string' ? col.title : undefined,
          price: typeof col.price === 'number' ? col.price : null,
        };
      })
      : [],
    rows: Array.isArray(row.rows)
      ? row.rows.filter((item) => item && typeof item === 'object').map((item) => {
        const spec = item as Record<string, unknown>;
        return { label: String(spec.label ?? ''), values: Array.isArray(spec.values) ? spec.values.map(String) : [] };
      })
      : [],
    summary: typeof row.summary === 'string' ? row.summary : undefined,
  };
}

function mapProductRef(value: unknown): PickiProductRef {
  const row = (value && typeof value === 'object' ? value : {}) as Record<string, unknown>;
  return {
    productId: typeof row.product_id === 'string' ? row.product_id : undefined,
    role: typeof row.role === 'string' ? row.role : undefined,
    badge: typeof row.badge === 'string' ? row.badge : undefined,
    title: typeof row.title === 'string' ? row.title : undefined,
    brand: typeof row.brand === 'string' ? row.brand : undefined,
    price: typeof row.price === 'number' ? row.price : null,
    specLine: typeof row.spec_line === 'string' ? row.spec_line : null,
  };
}

function mapDetailSection(value: unknown): PickiDetailSection {
  const row = (value && typeof value === 'object' ? value : {}) as Record<string, unknown>;
  return {
    id: String(row.id ?? ''),
    title: String(row.title ?? 'Details'),
    collapsed: row.collapsed !== false,
    lines: Array.isArray(row.lines) ? row.lines.map(String) : [],
  };
}

function mapSuggestedAction(value: unknown): SuggestedPickiAction {
  const row = (value && typeof value === 'object' ? value : {}) as Record<string, unknown>;
  const action = row.action === 'compare' || row.action === 'why_this' ? row.action : row.action === 'cheaper' ? 'cheaper' : undefined;
  return {
    id: String(row.id ?? ''),
    label: String(row.label ?? ''),
    kind: row.kind === 'quick' ? 'quick' : 'message',
    action,
    message: typeof row.message === 'string' ? row.message : undefined,
    href: typeof row.href === 'string' ? row.href : undefined,
  };
}

function mapProposedAction(value: unknown): ProposedShoppingAction {
  const row = (value && typeof value === 'object' ? value : {}) as Record<string, unknown>;
  const type = row.type === 'preference_update' ? 'preference_update' : 'cart_update';
  const status = ['proposed', 'validated', 'confirmed', 'executed', 'failed'].includes(String(row.status))
    ? (String(row.status) as ProposedShoppingAction['status'])
    : 'proposed';
  return {
    id: String(row.id ?? ''),
    type,
    summary: String(row.summary ?? ''),
    payload: row.payload && typeof row.payload === 'object' ? row.payload as Record<string, unknown> : {},
    status,
  };
}

function mapCard(value: unknown): LivePickCard | null {
  if (!value || typeof value !== 'object') return null;
  const card = value as Record<string, unknown>;
  const product = card.product;
  if (!product || typeof product !== 'object') return null;
  return {
    product: humanizeProduct(product as Product),
    whyForYou: String(card.why_for_you ?? ''),
    oneCaution: String(card.one_caution ?? ''),
    referencePrice: typeof card.reference_price === 'number' ? card.reference_price : null,
    priceLabel: typeof card.price_label === 'string' ? card.price_label : null,
    amazonUrl: typeof card.amazon_url === 'string' ? card.amazon_url : null,
    priceVerifiedAt: typeof card.price_verified_at === 'string' ? card.price_verified_at : null,
  };
}

function mapMemory(row: Record<string, unknown>): ShoppingMemory {
  const sourceType = row.source_type === 'inferred' ? 'inferred' : row.source === 'inferred' ? 'inferred' : 'explicit';
  const status = ['active', 'suggested', 'dismissed', 'superseded'].includes(String(row.status))
    ? (String(row.status) as ShoppingMemory['status'])
    : undefined;
  return {
    id: String(row.id),
    facet: String(row.facet ?? ''),
    value: String(row.value ?? ''),
    label: String(row.label ?? row.normalized_preference ?? ''),
    scope: String(row.scope ?? 'personal'),
    source: String(row.source ?? sourceType),
    evidence: typeof row.original_user_expression === 'string'
      ? row.original_user_expression
      : typeof row.evidence === 'string'
        ? row.evidence
        : null,
    enabled: row.enabled !== false && status !== 'dismissed',
    sourceType,
    status,
    userConfirmed: row.user_confirmed === true || sourceType === 'explicit',
    normalizedPreference: typeof row.normalized_preference === 'string' ? row.normalized_preference : undefined,
    originalUserExpression: typeof row.original_user_expression === 'string' ? row.original_user_expression : null,
    supportingEvidenceCount: typeof row.supporting_evidence_count === 'number' ? row.supporting_evidence_count : undefined,
    evidenceSnippets: mapEvidenceSnippets(row.evidence_message_ids),
    conversationIds: mapEvidenceConversationIds(row.evidence_message_ids),
    priority: typeof row.priority === 'number' ? row.priority : 50,
  };
}

function mapEvidenceConversationIds(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const ids: string[] = [];
  for (const item of value) {
    if (item && typeof item === 'object') {
      const id = (item as Record<string, unknown>).conversation_id;
      if (typeof id === 'string' && id && !ids.includes(id)) ids.push(id);
    }
  }
  return ids;
}

function mapEvidenceSnippets(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const lines: string[] = [];
  for (const item of value) {
    if (typeof item === 'string' && item.trim()) lines.push(item.trim());
    if (item && typeof item === 'object') {
      const row = item as Record<string, unknown>;
      const snippet = typeof row.snippet === 'string' ? row.snippet : typeof row.text === 'string' ? row.text : '';
      if (snippet.trim()) lines.push(snippet.trim());
    }
  }
  return lines;
}

function mapExplanation(value: unknown): ComparisonRecord['explanation'] {
  if (!value || typeof value !== 'object') return null;
  const row = value as Record<string, unknown>;
  return {
    winnerProductId: typeof row.winner_product_id === 'string' ? row.winner_product_id : null,
    headline: String(row.headline ?? ''),
    summary: String(row.summary ?? ''),
    verdict: typeof row.verdict === 'string' ? row.verdict : '',
    reasons: Array.isArray(row.reasons)
      ? row.reasons.filter((item) => item && typeof item === 'object').map((item) => {
        const reason = item as Record<string, unknown>;
        return { title: String(reason.title ?? ''), body: String(reason.body ?? '') };
      })
      : [],
    diffs: Array.isArray(row.diffs)
      ? row.diffs.filter((item) => item && typeof item === 'object').map((item) => {
        const diff = item as Record<string, unknown>;
        return { label: String(diff.label ?? ''), values: Array.isArray(diff.values) ? diff.values.map(String) : [] };
      })
      : [],
    preferenceNote: typeof row.preference_note === 'string' ? row.preference_note : null,
    limitation: typeof row.limitation === 'string' ? row.limitation : null,
  };
}

function mapComparison(row: Record<string, unknown>): ComparisonRecord {
  const products = Array.isArray(row.products) ? row.products : [];
  return {
    id: String(row.id),
    title: String(row.title ?? 'Comparison'),
    verdict: String(row.verdict ?? ''),
    winnerProductId: typeof row.winner_product_id === 'string' ? row.winner_product_id : null,
    conversationId: typeof row.conversation_id === 'string' ? row.conversation_id : null,
    createdAt: String(row.created_at ?? ''),
    explanation: mapExplanation(row.explanation),
    products: products.filter((item) => item && typeof item === 'object').map((item) => {
      const shot = item as Record<string, unknown>;
      return {
        productId: String(shot.product_id ?? ''),
        title: String(shot.title ?? ''),
        brand: String(shot.brand ?? ''),
        kind: String(shot.kind ?? 'other'),
        referencePrice: typeof shot.reference_price === 'number' ? shot.reference_price : null,
        rating: typeof shot.rating === 'number' ? shot.rating : null,
        reviewCount: typeof shot.review_count === 'number' ? shot.review_count : 0,
        feature: typeof shot.feature === 'string' ? shot.feature : null,
        caution: typeof shot.caution === 'string' ? shot.caution : null,
      };
    }),
  };
}

function mapCartItem(row: Record<string, unknown>): CartItem {
  const product = row.product && typeof row.product === 'object' ? humanizeProduct(row.product as Product) : undefined;
  return {
    id: String(row.id),
    productId: String(row.product_id ?? ''),
    conversationId: typeof row.conversation_id === 'string' ? row.conversation_id : null,
    sourceType: String(row.source_type ?? 'product'),
    title: String(row.title ?? product?.name ?? ''),
    price: typeof row.price === 'number' ? row.price : null,
    createdAt: String(row.created_at ?? ''),
    product,
  };
}

function mapSavedPick(row: Record<string, unknown>): SavedPick {
  const product = row.product && typeof row.product === 'object' ? humanizeProduct(row.product as Product) : undefined;
  return {
    id: String(row.id),
    productId: String(row.product_id ?? ''),
    conversationId: typeof row.conversation_id === 'string' ? row.conversation_id : null,
    reason: String(row.reason ?? ''),
    title: String(row.title ?? product?.name ?? ''),
    price: typeof row.price === 'number' ? row.price : null,
    createdAt: String(row.created_at ?? ''),
    product,
  };
}

function mapMemoryEvent(value: unknown): MemoryEvent {
  if (!value || typeof value !== 'object') return null;
  const event = value as Record<string, unknown>;
  if (!event.id || !event.label) return null;
  return { id: String(event.id), label: String(event.label) };
}
