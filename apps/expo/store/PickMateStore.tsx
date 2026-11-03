import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createEvent } from '../lib/behavior';
import { parseIntent } from '../lib/intent';
import { humanizeProduct, humanizeRecommendationResult } from '../lib/presentation';
import { buildDecisionContext, defaultShoppingDecisionProfile, handleProfileUpdate, updateInferredPreference } from '../lib/profile';
import { applyServerProfile, inferredToRankingKey, rankingKeyFromClient } from '../lib/shoppingProfile';
import { conversationTitle, pickiMessage, productIdsInMessages, replyFromFind, replyFromProduct, youMessage, type PickiChatMessage } from '../lib/pickiTalk';
import { productTitle } from '../lib/format';
import { QUICK_ACTION_LABELS, type CartItem, type ComparisonRecord, type LivePickCard, type MemoryEvent, type PickAction, type RelatedChat, type SavedPick, type ShoppingMemory, type StructuredPickiResponse } from '../lib/shoppingTurn';
import type { BrowsingEvent, Product, RecommendationResult, ShoppingDecisionProfile, UserIntent } from '../types';
import { readJson, writeJson } from '../services/storage/storage';
import { PickMateApiClient } from '../services/api/client';
import { DEMO_MODE, preferredDemoConversationId, readDemoConversationSelection, rememberDemoConversationSelection } from '../lib/demo';

const exampleNeed = '';
const PROFILE_KEY = 'pickmate_expo_profile';
const SAVED_KEY = 'pickmate_expo_saved';
const initialIntent = parseIntent('');

type SavedDecision = {
  id: string;
  createdAt: string;
  userNeed: string;
  result: RecommendationResult;
};

export type PickiConversationSummary = {
  id: string;
  title: string;
  updatedAt: string;
  contextProductId?: string | null;
  manualTitle?: boolean;
};

type PickMateStore = {
  products: Product[];
  catalogCount: number | null;
  need: string;
  intent: UserIntent;
  result: RecommendationResult;
  compareIds: string[];
  saved: SavedDecision[];
  events: BrowsingEvent[];
  profile: ShoppingDecisionProfile;
  loadingProducts: boolean;
  runningDecision: boolean;
  conversationHydrating: boolean;
  error: string | null;
  runRecommendation: (text?: string, candidateIds?: string[], currentProductId?: string, endpoint?: 'recommend' | 'update' | 'compare' | 'decide' | 'price-check' | 'product-question') => Promise<RecommendationResult>;
  reloadProducts: () => Promise<void>;
  openQuickTake: (productId: string, originConversationId?: string | null) => void;
  openPickiFind: (text: string) => void;
  closeQuickTake: () => void;
  followUpQuickTake: (text: string) => Promise<void>;
  sendPickiMessage: (text: string) => Promise<void>;
  pickiOpen: boolean;
  pickiWorkspaceActive: boolean;
  pickiMessages: PickiChatMessage[];
  pickiProductId: string | null;
  quickTakeProductId: string | null;
  quickTakeResult: RecommendationResult | null;
  quickTakeLoading: boolean;
  quickTakeError: string | null;
  decisionStatus: string | null;
  updateNeed: (text: string) => string;
  toggleCompare: (id: string) => void;
  track: (name: BrowsingEvent['name'], productId?: string) => void;
  saveCurrentDecision: () => void;
  confirmInferredPreference: (key: string) => void;
  dismissInferredPreference: (key: string) => void;
  updateConfirmedPreference: (key: string, payload: { weight?: number; value?: unknown }) => void;
  removeConfirmedPreference: (key: string) => void;
  getProduct: (id: string | string[] | undefined) => Product | undefined;
  ensureProduct: (id: string) => Promise<Product | undefined>;
  searchCatalog: (params?: { q?: string; brand?: string; maxPrice?: number | null; sort?: string; offset?: number; limit?: number }) => Promise<{ items: Product[]; count: number }>;
  catalogBrands: string[];
  resumeDecision: () => void;
  hasResumableDecision: boolean;
  conversations: PickiConversationSummary[];
  activeConversationId: string | null;
  startNewConversation: (contextProductId?: string | null) => Promise<void>;
  openProductInPicki: (productId: string) => Promise<void>;
  renameConversation: (id: string, title: string) => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;
  selectConversation: (id: string, options?: { keepOverlay?: boolean; contextProductId?: string }) => Promise<void>;
  livePick: LivePickCard | null;
  liveAlternatives: LivePickCard[];
  quickActions: Array<'cheaper' | 'different_style' | 'compare' | 'why_this'>;
  changedSinceLastPick: string[];
  memoryEvent: MemoryEvent;
  shoppingMemories: ShoppingMemory[];
  memoryEnabled: boolean;
  savedPicks: SavedPick[];
  sendQuickAction: (action: 'cheaper' | 'different_style' | 'compare' | 'why_this') => Promise<void>;
  promoteAlternative: (productId: string) => Promise<void>;
  saveActivePick: () => Promise<void>;
  forgetShoppingMemory: (id: string) => Promise<void>;
  undoTasteSaved: (ids: string[]) => Promise<void>;
  saveShoppingPreference: (id: string, label: string) => Promise<void>;
  confirmShoppingPreference: (id: string) => Promise<void>;
  setShoppingPreferencePriority: (id: string, priority: number) => Promise<void>;
  dismissShoppingPreference: (id: string) => Promise<void>;
  setMemoryEnabled: (enabled: boolean) => Promise<void>;
  removeSavedPick: (productId: string) => Promise<void>;
  cart: CartItem[];
  cartSelected: string[];
  addToCart: (productId: string, source: { conversationId?: string | null; sourceType: 'chat' | 'product' }) => Promise<void>;
  cartNotice: { productId: string; already: boolean } | null;
  dismissCartNotice: () => void;
  removeFromCart: (productId: string) => Promise<void>;
  toggleCartSelected: (productId: string) => void;
  setCartSelected: (productIds: string[]) => void;
  compareSelection: () => Promise<void>;
  removeSelectedFromCart: () => Promise<void>;
  comparisons: ComparisonRecord[];
  activeComparison: ComparisonRecord | null;
  closeComparison: () => void;
  openComparison: (record: ComparisonRecord) => void;
  askAboutComparison: () => Promise<void>;
  keepComparisonPick: () => Promise<void>;
  pendingComparison: ComparisonRecord | null;
  relatedChats: (productId: string) => Promise<RelatedChat[]>;
  relatedChatsForProducts: (productIds: string[]) => Promise<RelatedChat[]>;
  addTaste: (label: string) => Promise<void>;
  openFullChat: () => void;
  setPickiWorkspaceActive: (active: boolean) => void;
  confirmAgentAction: (action: { type: 'cart_update' | 'preference_update'; payload: Record<string, unknown> }) => Promise<{ ok: boolean; message: string }>;
};

const StoreContext = createContext<PickMateStore | null>(null);

export function PickMateProvider({ children }: { children: React.ReactNode }) {
  const [need, setNeed] = useState(exampleNeed);
  const [intent, setIntent] = useState(initialIntent);
  const [events, setEvents] = useState<BrowsingEvent[]>([]);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [profile, setProfile] = useState(defaultShoppingDecisionProfile);
  const [saved, setSaved] = useState<SavedDecision[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [productCache, setProductCache] = useState<Record<string, Product>>({});
  const [catalogCount, setCatalogCount] = useState<number | null>(null);
  const [catalogBrands, setCatalogBrands] = useState<string[]>([]);
  const [hasResumableDecision, setHasResumableDecision] = useState(false);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [runningDecision, setRunningDecision] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quickTakeProductId, setQuickTakeProductId] = useState<string | null>(null);
  const [quickTakeResult, setQuickTakeResult] = useState<RecommendationResult | null>(null);
  const [quickTakeLoading, setQuickTakeLoading] = useState(false);
  const [quickTakeError, setQuickTakeError] = useState<string | null>(null);
  const [quickTakeToken, setQuickTakeToken] = useState(0);
  const [decisionStatus, setDecisionStatus] = useState<string | null>(null);
  const [pickiOpen, setPickiOpen] = useState(false);
  const [pickiWorkspaceActive, setPickiWorkspaceActiveState] = useState(false);
  const [pickiMessages, setPickiMessages] = useState<PickiChatMessage[]>([]);
  const [conversations, setConversations] = useState<PickiConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const activeConversationIdRef = useRef<string | null>(null);
  const conversationLoadTokenRef = useRef(0);
  const openProductRequestRef = useRef<Promise<void> | null>(null);
  const [conversationHydrating, setConversationHydrating] = useState(false);
  const [livePick, setLivePick] = useState<LivePickCard | null>(null);
  const [liveAlternatives, setLiveAlternatives] = useState<LivePickCard[]>([]);
  const [quickActions, setQuickActions] = useState<Array<'cheaper' | 'different_style' | 'compare' | 'why_this'>>([]);
  const [changedSinceLastPick, setChangedSinceLastPick] = useState<string[]>([]);
  const [memoryEvent, setMemoryEvent] = useState<MemoryEvent>(null);
  const [shoppingMemories, setShoppingMemories] = useState<ShoppingMemory[]>([]);
  const [memoryEnabled, setMemoryEnabledState] = useState(true);
  const [savedPicks, setSavedPicks] = useState<SavedPick[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [cartNotice, setCartNotice] = useState<{ productId: string; already: boolean } | null>(null);
  const [cartSelected, setCartSelectedState] = useState<string[]>([]);
  const [comparisons, setComparisons] = useState<ComparisonRecord[]>([]);
  const [activeComparison, setActiveComparison] = useState<ComparisonRecord | null>(null);
  const [pendingProductId, setPendingProductId] = useState<string | null>(null);
  const [pendingComparison, setPendingComparison] = useState<ComparisonRecord | null>(null);
  const pickiProductId = quickTakeProductId;
  const api = useMemo(() => new PickMateApiClient(AsyncStorage), []);
  const context = useMemo(() => buildDecisionContext(intent, events, profile), [events, intent, profile]);

  const [result, setResult] = useState<RecommendationResult>(() => emptyResult(initialIntent));

  function activateConversation(id: string | null) {
    conversationLoadTokenRef.current += 1;
    setConversationHydrating(false);
    activeConversationIdRef.current = id;
    setActiveConversationId(id);
    if (DEMO_MODE) rememberDemoConversationSelection(id);
  }

  useEffect(() => {
    readJson(PROFILE_KEY, defaultShoppingDecisionProfile).then(setProfile);
    readJson<SavedDecision[]>(SAVED_KEY, []).then((items) => setSaved(items.map(humanizeSavedDecision)));
    void reloadProducts();
    api.savedDecisions().then((items) => setSaved(items.map(humanizeSavedDecision))).catch(() => undefined);
    (async () => {
      const [items, nextCart, memory, nextSavedPicks, nextComparisons, serverProfile] = await Promise.all([
        api.listConversations(),
        api.cart(),
        api.shoppingMemories(),
        api.savedPicks(),
        api.comparisons(),
        api.profile(),
      ]);
      setCart(nextCart);
      setShoppingMemories(memory.items);
      setMemoryEnabledState(memory.memoryEnabled);
      setSavedPicks(nextSavedPicks);
      setComparisons(nextComparisons);
      if (serverProfile && typeof serverProfile === 'object') {
        setProfile((current) => persistLocal(applyServerProfile(serverProfile as Record<string, unknown>, current)));
      }
      return items;
    })().then(async (items) => {
      if (!items) return;
      setConversations(items);
      const initialConversationId = DEMO_MODE
        ? preferredDemoConversationId(items, readDemoConversationSelection())
        : items[0]?.id ?? null;
      if (!initialConversationId) return;
      await selectConversation(initialConversationId);
    }).catch(() => undefined);
  }, [api]);

  async function reloadProducts() {
    setLoadingProducts(true);
    setError(null);
    try {
      const catalog = await api.catalog();
      if (catalog.catalog !== 'amazon_home_audio' || catalog.schema !== 'ecomagentbench_product_db') {
        setProducts([]);
        setCatalogCount(null);
        throw new Error('The API is not connected to the authorized Amazon Home Audio & Theater catalog.');
      }
      const preview = await api.products({ limit: 8, sort: 'reviews' });
      const items = preview.items.map(humanizeProduct).filter((item) => item.category === 'Home Audio & Theater');
      setCatalogCount(catalog.product_count);
      setCatalogBrands(catalog.brands ?? []);
      setProducts((current) => items.map((item) => mergeCatalogProduct(current.find((product) => product.id === item.id), item)));
      setProductCache((current) => {
        const next = { ...current };
        for (const item of items) next[item.id] = mergeCatalogProduct(current[item.id], item);
        return next;
      });
      if (!items.length) setError('The catalog did not return any available products.');
      try {
        const session = await api.decisionState();
        if (session?.state && typeof session.state === 'object') setHasResumableDecision(true);
      } catch {
        setHasResumableDecision(false);
      }
    } catch (requestError) {
      setProducts([]);
      setCatalogCount(null);
      setError(requestError instanceof Error ? requestError.message : 'The catalog could not be loaded.');
    } finally {
      setLoadingProducts(false);
    }
  }

  async function runRecommendation(
    text = need,
    candidateIds = compareIds.length ? compareIds : undefined,
    currentProductId?: string,
    endpoint?: 'recommend' | 'update' | 'compare' | 'decide' | 'price-check' | 'product-question',
  ) {
    if (!text.trim()) throw new Error('Tell Picki what you are looking for first.');
    const nextIntent = parseIntent(text, intent);
    setNeed(text);
    setIntent(nextIntent);
    setRunningDecision(true);
    setDecisionStatus('Filtering products that meet your requirements…');
    setError(null);
    const action = endpoint
      || (candidateIds?.length && candidateIds.length > 1 ? 'compare' : currentProductId ? 'product-question' : 'recommend');
    try {
      const nextResult = humanizeRecommendationResult(await api.recommend(
        text,
        candidateIds ?? [],
        currentProductId,
        action,
      ));
      setResult(nextResult);
      setHasResumableDecision(true);
      api.saveDecisionState({
        message: text,
        runId: nextResult.id,
        primaryId: nextResult.primaryRecommendation?.product.id,
      }).catch(() => undefined);
      track('decision_generated');
      return nextResult;
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : 'Picki could not complete this analysis right now.';
      setError(message);
      throw requestError;
    } finally {
      setRunningDecision(false);
      setDecisionStatus(null);
    }
  }

  async function ensureActiveConversation() {
    if (activeConversationId) return activeConversationId;
    const product = pendingProductId ? productCache[pendingProductId] || products.find((item) => item.id === pendingProductId) : undefined;
    const title = pendingComparison
      ? 'Compare products in My Picks'
      : product
        ? `Analyze ${productTitle(product)}`.slice(0, 42)
        : 'New conversation';
    const row = await api.createConversation({ title, state: { messages: [], productId: pendingProductId } });
    const id = row.id;
    activateConversation(row.id);
    setConversations((current) => [{ id: row.id, title: row.title, updatedAt: row.updatedAt, contextProductId: pendingProductId }, ...current.filter((item) => item.id !== row.id)]);
    if (pendingComparison) {
      const record = pendingComparison;
      setPickiMessages((current) => current.length ? current : [pickiMessage('I brought in the products you selected. What matters most: compatibility, performance, or price?')]);
      void api.linkComparison(record.id, id).then((linked) => {
        setComparisons((current) => current.map((item) => item.id === linked.id ? linked : item));
      }).catch(() => undefined);
      setPendingComparison(null);
    }
    if (pendingProductId) setPendingProductId(null);
    return id;
  }

  function clearBoard() {
    setLivePick(null);
    setLiveAlternatives([]);
    setQuickActions([]);
    setChangedSinceLastPick([]);
    setMemoryEvent(null);
  }

  function restoreBoard(state: Record<string, unknown>) {
    setLivePick(state.livePick && typeof state.livePick === 'object' ? state.livePick as LivePickCard : null);
    setLiveAlternatives(Array.isArray(state.liveAlternatives) ? state.liveAlternatives as LivePickCard[] : []);
    setQuickActions(Array.isArray(state.quickActions) ? state.quickActions as Array<'cheaper' | 'different_style' | 'compare' | 'why_this'> : []);
    setChangedSinceLastPick(Array.isArray(state.changedSinceLastPick) ? state.changedSinceLastPick.map(String) : []);
    setMemoryEvent(null);
  }

  function rememberProducts(cards: Array<LivePickCard | null>) {
    setProductCache((current) => {
      const next = { ...current };
      for (const card of cards) {
        if (card?.product) next[card.product.id] = card.product;
      }
      return next;
    });
  }

  async function hydrateReferencedProducts(messages: PickiChatMessage[]) {
    const missing = productIdsInMessages(messages).filter((id) => !productCache[id]);
    if (!missing.length) return;
    const loaded = await Promise.all(missing.map((id) => api.product(id).catch(() => null)));
    setProductCache((current) => {
      const next = { ...current };
      for (const item of loaded) {
        if (!item?.id) continue;
        next[item.id] = mergeCatalogProduct(current[item.id], humanizeProduct(item));
      }
      return next;
    });
  }

  async function refreshShoppingMemory() {
    const memory = await api.shoppingMemories();
    setShoppingMemories(memory.items);
    setMemoryEnabledState(memory.memoryEnabled);
  }

  async function sendShoppingTurn(input: { message?: string; action?: PickAction; productId?: string; echo?: string; conversationId?: string }) {
    const conversationId = input.conversationId || await ensureActiveConversation();
    const echo = input.echo ?? input.message;
    if (echo?.trim()) setPickiMessages((current) => [...current, youMessage(echo.trim())]);
    if (!pickiWorkspaceActive) setPickiOpen(true);
    setRunningDecision(true);
    setDecisionStatus('Checking real products and available evidence…');
    setError(null);
    setMemoryEvent(null);
    try {
      const turn = await api.pickiTurn({
        conversationId,
        message: input.message ?? '',
        action: input.action ?? 'message',
        productId: input.productId,
      });
      // The server persists the response to its originating conversation. If
      // the user navigated elsewhere through another entry point while this
      // request was pending, do not leak A's transient UI state into B.
      if (activeConversationIdRef.current !== conversationId) return;
      setLivePick(turn.activePick);
      setLiveAlternatives(turn.alternatives);
      setQuickActions(turn.quickActions);
      setChangedSinceLastPick(turn.changedSinceLastPick);
      setMemoryEvent(turn.memoryEvent);
      rememberProducts([turn.activePick, ...turn.alternatives]);
      if (input.message?.trim()) setNeed(input.message.trim());
      setHasResumableDecision(Boolean(turn.activePick));
      setPickiMessages((current) => [...current, pickiMessage(turn.message, turn.activePick ? {
        product: turn.activePick.product,
        why: turn.activePick.whyForYou,
        check: turn.activePick.oneCaution,
        structured: turn.structuredResponse ?? null,
        proposedActions: turn.proposedActions ?? [],
        tasteSaved: turn.tasteSaved ?? null,
      } : {
        structured: turn.structuredResponse ?? null,
        proposedActions: turn.proposedActions ?? [],
        tasteSaved: turn.tasteSaved ?? null,
      })]);
      // Chat-side save actions are persisted server-side to the same list used
      // by “我的清单”; refresh both compatibility views before reporting done.
      if (/\b(save|bookmark)\b|保存|保留.{0,4}清单/i.test(input.message ?? '')) {
        const [nextCart, nextSaved] = await Promise.all([api.cart(), api.savedPicks()]);
        setCart(nextCart);
        setSavedPicks(nextSaved);
      }
      if (turn.tasteSaved || turn.memoryEvent) void refreshShoppingMemory();
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : 'Picki could not complete this analysis right now.';
      setPickiMessages((current) => [...current, pickiMessage(message)]);
      setError(message);
    } finally {
      setRunningDecision(false);
      setDecisionStatus(null);
    }
  }

  function openPickiFind(text: string) {
    const value = text.trim();
    if (!value) return;
    setQuickTakeProductId(null);
    void sendShoppingTurn({ message: value });
  }

  async function startNewConversation(contextProductId: string | null = null) {
    if (runningDecision) return;
    const product = contextProductId ? productCache[contextProductId] || products.find((item) => item.id === contextProductId) : undefined;
    const title = product ? `Analyze ${productTitle(product)}`.slice(0, 42) : 'New conversation';
    const row = await api.createConversation({ title, state: { messages: [], productId: contextProductId } });
    activateConversation(row.id);
    setConversations((current) => [{ id: row.id, title: row.title, updatedAt: row.updatedAt, contextProductId }, ...current.filter((item) => item.id !== row.id)]);
    setPendingProductId(null);
    setPendingComparison(null);
    setPickiMessages([]);
    setNeed('');
    setIntent(initialIntent);
    setResult(emptyResult(initialIntent));
    setQuickTakeProductId(contextProductId);
    setQuickTakeResult(null);
    setPickiOpen(false);
    setError(null);
    clearBoard();
  }

  async function renameConversation(id: string, title: string) {
    if (runningDecision) return;
    const normalized = title.trim();
    if (!normalized) return;
    const row = await api.renameConversation(id, normalized);
    setConversations((current) => current.map((item) => item.id === id ? { ...item, title: row.title, updatedAt: row.updatedAt, manualTitle: true } : item));
  }

  async function deleteConversation(id: string) {
    if (runningDecision) return;
    await api.deleteConversation(id);
    const remaining = conversations.filter((item) => item.id !== id);
    setConversations(remaining);
    if (activeConversationId !== id) return;
    if (remaining[0]) {
      await selectConversation(remaining[0].id);
    } else {
      activateConversation(null);
      setPickiMessages([]);
      setNeed('');
      setQuickTakeProductId(null);
      clearBoard();
    }
  }

  async function selectConversation(id: string, options?: { keepOverlay?: boolean; contextProductId?: string }) {
    if (runningDecision) return;
    setPendingProductId(null);
    setPendingComparison(null);
    activateConversation(id);
    setConversationHydrating(true);
    const loadToken = conversationLoadTokenRef.current;
    const isCurrentLoad = () => loadToken === conversationLoadTokenRef.current && activeConversationIdRef.current === id;
    setPickiMessages([]);
    if (options?.keepOverlay) setPickiOpen(true);
    else setPickiOpen(false);
    try {
      const row = await api.getConversation(id);
      if (!isCurrentLoad()) return;
      const state = row.state || {};
      const messages = Array.isArray(state.messages) ? state.messages as PickiChatMessage[] : [];
      setPickiMessages(messages);
      await hydrateReferencedProducts(messages);
      if (!isCurrentLoad()) return;
      setNeed(typeof state.need === 'string' ? state.need : '');
      if (state.result && typeof state.result === 'object') setResult(state.result as RecommendationResult);
      const contextProductId = options?.contextProductId ?? (typeof state.productId === 'string' ? state.productId : null);
      setQuickTakeProductId(contextProductId);
      setConversations((current) => current.map((item) => item.id === id ? { ...item, contextProductId } : item));
      restoreBoard(state);
    } catch {
      if (isCurrentLoad()) setPickiMessages([]);
    } finally {
      if (isCurrentLoad()) setConversationHydrating(false);
    }
  }

  async function openProductInPicki(productId: string) {
    if (openProductRequestRef.current) return openProductRequestRef.current;
    const request = (async () => {
      const product = productCache[productId] || products.find((item) => item.id === productId);
      const row = await api.createConversation({
        title: product ? `Analyze ${productTitle(product)}`.slice(0, 42) : 'Product analysis',
        state: { messages: [], productId, manualTitle: true },
      });
      activateConversation(row.id);
      setConversations((current) => [{ id: row.id, title: row.title, updatedAt: row.updatedAt, contextProductId: productId }, ...current.filter((item) => item.id !== row.id)]);
      setPickiMessages([]);
      setNeed('');
      setQuickTakeProductId(productId);
      setPickiOpen(false);
      setError(null);
      clearBoard();
      await sendShoppingTurn({
        conversationId: row.id,
        message: 'Analyze this product using its catalog specifications, available verified review evidence, and my confirmed preferences. Do not assume requirements I have not provided.',
        echo: 'Analyze this product',
        productId,
      });
      track('picki_opened', productId);
    })();
    openProductRequestRef.current = request;
    try {
      await request;
    } finally {
      if (openProductRequestRef.current === request) openProductRequestRef.current = null;
    }
  }

  function openQuickTake(productId: string, originConversationId?: string | null) {
    if (originConversationId) {
      setPendingProductId(null);
      setPendingComparison(null);
      setPickiOpen(true);
      void selectConversation(originConversationId, { keepOverlay: true });
      return;
    }
    activateConversation(null);
    setPendingComparison(null);
    setPendingProductId(productId);
    setQuickTakeProductId(productId);
    setPickiMessages([]);
    setPickiOpen(true);
    clearBoard();
    track('picki_opened', productId);
  }

  function closeQuickTake() {
    setQuickTakeToken(Date.now());
    setPickiOpen(false);
    setQuickTakeLoading(false);
    setQuickTakeError(null);
  }

  async function sendPickiMessage(text: string) {
    if (conversationHydrating) return;
    const value = text.trim();
    if (!value) return;
    await sendShoppingTurn({ message: value, productId: quickTakeProductId ?? undefined });
  }

  async function sendQuickAction(action: 'cheaper' | 'different_style' | 'compare' | 'why_this') {
    if (conversationHydrating) return;
    await sendShoppingTurn({ action, echo: QUICK_ACTION_LABELS[action] });
  }

  async function promoteAlternative(productId: string) {
    await sendShoppingTurn({ action: 'promote', productId, echo: 'Make this my top choice' });
  }

  async function saveActivePick() {
    if (!livePick) return;
    await api.savePick(livePick.product.id, activeConversationId, livePick.whyForYou);
    setSavedPicks(await api.savedPicks());
  }

  async function forgetShoppingMemory(id: string) {
    await api.forgetMemory(id);
    setMemoryEvent((current) => current?.id === id ? null : current);
    await refreshShoppingMemory();
  }

  async function saveShoppingPreference(id: string, label: string) {
    await api.patchMyTaste(id, { label, normalizedPreference: label, userConfirmed: true });
    await refreshShoppingMemory();
  }

  async function confirmShoppingPreference(id: string) {
    await api.patchMyTaste(id, { status: 'active', userConfirmed: true });
    await refreshShoppingMemory();
  }

  async function setShoppingPreferencePriority(id: string, priority: number) {
    await api.patchMyTaste(id, { priority });
    await refreshShoppingMemory();
  }

  async function dismissShoppingPreference(id: string) {
    await api.patchMyTaste(id, { status: 'dismissed', userConfirmed: false });
    await refreshShoppingMemory();
  }

  async function undoTasteSaved(ids: string[]) {
    const unique = [...new Set(ids.filter(Boolean))];
    for (const id of unique) await api.forgetMemory(id);
    setPickiMessages((current) => current.map((message) => (
      message.tasteSaved && unique.some((id) => message.tasteSaved?.ids.includes(id))
        ? { ...message, tasteSaved: null }
        : message
    )));
    await refreshShoppingMemory();
  }

  async function setMemoryEnabled(enabled: boolean) {
    setMemoryEnabledState(enabled);
    await api.setShoppingMemory(enabled);
  }

  async function removeSavedPick(productId: string) {
    await api.removeSavedPick(productId);
    setSavedPicks((current) => current.filter((item) => item.productId !== productId));
  }

  async function refreshCart() {
    setCart(await api.cart());
  }

  async function addToCart(productId: string, source: { conversationId?: string | null; sourceType: 'chat' | 'product' }) {
    const already = cart.some((item) => item.productId === productId);
    await api.addCartItem(productId, source.sourceType === 'chat' ? source.conversationId ?? null : null, source.sourceType);
    await refreshCart();
    setCartNotice({ productId, already });
  }

  function dismissCartNotice() {
    setCartNotice(null);
  }

  async function removeFromCart(productId: string) {
    await api.removeCartItem(productId);
    setCartSelectedState((current) => current.filter((id) => id !== productId));
    await refreshCart();
  }

  function toggleCartSelected(productId: string) {
    setCartSelectedState((current) => current.includes(productId) ? current.filter((id) => id !== productId) : [...current, productId]);
  }

  function setCartSelected(productIds: string[]) {
    setCartSelectedState(productIds);
  }

  async function compareSelection() {
    if (cartSelected.length < 2 || cartSelected.length > 4) return;
    const record = await api.createComparison(cartSelected);
    setComparisons((current) => [record, ...current.filter((item) => item.id !== record.id)]);
    setActiveComparison(record);
  }

  async function continueComparisonInPicki(record: ComparisonRecord) {
    const selected = record.products.slice(0, 2);
    const winner = selected.find((item) => item.productId === record.winnerProductId);
    const comparisonSummary = winner
      ? record.explanation?.verdict || record.verdict || `${winner.title} is the better fit for the requirements you shared.`
      : record.explanation?.verdict || record.verdict || 'These products fit different situations, so I need one more detail before choosing between them.';
    const dimensionLabels: Record<string, string> = {
      video: 'Video', connectors: 'Connectors', connector: 'Connector', length: 'Distance', price: 'Price', rating: 'Rating', reviews: 'Review evidence', kind: 'Use case', feature: 'Key specification', caution: 'Main risk',
    };
    const structured: StructuredPickiResponse = {
      message: comparisonSummary,
      responseType: 'COMPARE',
      primaryMessage: comparisonSummary,
      productRefs: selected.map((item, index) => ({
        productId: item.productId,
        role: item.productId === record.winnerProductId ? 'primary' : index === 0 ? 'primary' : 'alternative',
        title: item.title,
        brand: item.brand,
        price: item.referencePrice,
        specLine: item.feature,
      })),
      comparisonData: {
        winnerProductId: record.winnerProductId,
        columns: selected.map((item) => ({ productId: item.productId, title: item.title, price: item.referencePrice })),
        rows: (record.explanation?.diffs || []).slice(0, 4).map((row) => ({ ...row, label: dimensionLabels[row.label.toLowerCase()] || row.label })),
        summary: comparisonSummary,
      },
      detailSections: [{
        id: 'comparison-limit',
        title: 'Evidence and limits',
        collapsed: true,
        lines: ['Specifications and prices come from the current catalog. Missing review evidence is not used to infer long-term reliability.'],
      }],
      suggestedActions: [
        { id: 'replace', label: 'Replace a product', kind: 'message', message: 'I want to replace one of the products in this comparison.' },
        { id: 'evidence', label: 'View review evidence', kind: 'message', message: 'Show me the review evidence used in this comparison.' },
      ],
    };
    const comparisonRequest = youMessage('Compare the two products I selected and explain the tradeoffs.');
    const firstMessage = pickiMessage(comparisonSummary, { structured });
    const row = await api.createConversation({
      title: `Compare: ${selected.map((item) => item.title).join(' vs. ')}`.slice(0, 80),
      state: { messages: [comparisonRequest, firstMessage], comparedProductIds: selected.map((item) => item.productId), manualTitle: true },
    });
    await api.linkComparison(record.id, row.id);
    activateConversation(row.id);
    setConversations((current) => [{ id: row.id, title: row.title, updatedAt: row.updatedAt }, ...current.filter((item) => item.id !== row.id)]);
    setPickiMessages([comparisonRequest, firstMessage]);
    setNeed('');
    setQuickTakeProductId(null);
    clearBoard();
  }

  async function removeSelectedFromCart() {
    const ids = [...cartSelected];
    if (!ids.length) return;
    for (const productId of ids) await api.removeCartItem(productId);
    setCartSelectedState([]);
    await refreshCart();
  }

  function closeComparison() {
    setActiveComparison(null);
  }

  function openComparison(record: ComparisonRecord) {
    setActiveComparison(record);
  }

  async function askAboutComparison() {
    if (!activeComparison) return;
    const record = activeComparison;
    await continueComparisonInPicki(record);
    setPickiOpen(false);
    setActiveComparison(null);
  }

  async function keepComparisonPick() {
    const winnerId = activeComparison?.winnerProductId || activeComparison?.explanation?.winnerProductId;
    if (!winnerId) return;
    await api.savePick(winnerId, activeComparison?.conversationId ?? null, activeComparison?.explanation?.headline || activeComparison?.verdict || 'Saved from a comparison');
    setSavedPicks(await api.savedPicks());
    setActiveComparison(null);
  }

  async function relatedChats(productId: string) {
    return api.productConversations(productId);
  }

  async function relatedChatsForProducts(productIds: string[]) {
    return api.relatedConversations(productIds);
  }

  async function addTaste(label: string) {
    await api.addTaste(label);
    await refreshShoppingMemory();
  }

  function openFullChat() {
    setPickiOpen(false);
  }

  function setPickiWorkspaceActive(active: boolean) {
    setPickiWorkspaceActiveState(active);
    if (active) setPickiOpen(false);
  }

  async function confirmAgentAction(action: { type: 'cart_update' | 'preference_update'; payload: Record<string, unknown> }) {
    try {
      const result = await api.executeAgentAction({
        conversationId: activeConversationId ?? undefined,
        type: action.type,
        payload: action.payload,
      });
      if (result.status !== 'executed') {
        return { ok: false, message: result.reason || 'Picki could not complete that action.' };
      }
      await refreshCart();
      await refreshShoppingMemory();
      return { ok: true, message: action.type === 'cart_update' ? 'My Picks updated.' : 'Preference saved.' };
    } catch (requestError) {
      return { ok: false, message: requestError instanceof Error ? requestError.message : 'The action failed. Please try again.' };
    }
  }

  async function followUpQuickTake(text: string) {
    const productId = quickTakeProductId;
    const value = text.trim();
    if (!productId || !value) return;
    const token = quickTakeToken;
    setQuickTakeLoading(true);
    setQuickTakeError(null);
    const prompt = need.trim() ? `${need}. ${value}` : value;
    try {
      const nextResult = humanizeRecommendationResult(await api.recommend(prompt, [productId], productId, 'product-question'));
      const product = products.find((item) => item.id === productId) || productCache[productId] || nextResult.primaryRecommendation?.product;
      if (token === quickTakeToken) {
        setQuickTakeResult(nextResult);
        if (product) setPickiMessages((current) => [...current, replyFromProduct(product, nextResult, need)]);
      }
    } catch (requestError) {
      if (token === quickTakeToken) {
        setQuickTakeError(requestError instanceof Error ? requestError.message : 'Picki could not answer that follow-up right now.');
        setPickiMessages((current) => [...current, pickiMessage(requestError instanceof Error ? requestError.message : 'Picki could not answer that follow-up right now.')]);
      }
    } finally {
      if (token === quickTakeToken) setQuickTakeLoading(false);
    }
  }

  function updateNeed(text: string) {
    const update = handleProfileUpdate(text, context.profileSnapshot);
    const nextProfile = update.changed ? update.profile : profile;
    if (update.changed) persistLocal(nextProfile);
    const nextIntent = parseIntent(text, intent);
    setNeed(text);
    setIntent(nextIntent);
    setRunningDecision(true);
    setDecisionStatus('Re-evaluating with the new condition…');
    api.recommend(text, compareIds, undefined, 'update')
      .then((nextResult) => setResult(humanizeRecommendationResult(nextResult)))
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : 'This decision could not be updated right now.'))
      .finally(() => {
        setRunningDecision(false);
        setDecisionStatus(null);
      });
    return update.message;
  }

  function toggleCompare(id: string) {
    setCompareIds((current) => {
      const next = current.includes(id) ? current.filter((item) => item !== id) : [...current, id];
      track(current.includes(id) ? 'product_removed_from_compare' : 'product_added_to_compare', id);
      return next;
    });
  }

  function track(name: BrowsingEvent['name'], productId?: string) {
    setEvents((current) => [...current, createEvent(name, productId)]);
    api.event(name, productId).catch(() => undefined);
  }

  function saveCurrentDecision() {
    if (!result.primaryRecommendation) return;
    const next = [{ id: `decision-${Date.now()}`, createdAt: new Date().toISOString(), userNeed: need, result: humanizeRecommendationResult(result) }, ...saved];
    setSaved(next);
    writeJson(SAVED_KEY, next);
    api.saveDecision(need, result).catch(() => undefined);
  }

  function confirmInferredPreference(key: string) {
    const next = updateInferredPreference(context.profileSnapshot, key, 'confirmed');
    const rankingKey = inferredToRankingKey(key);
    if (rankingKey) {
      const camel = rankingKey === 'noise_cancellation' ? 'noiseCancellation' : rankingKey === 'price_value' ? 'priceValue' : rankingKey;
      next.longTerm.stablePriorities[camel] = next.longTerm.stablePriorities[camel] ?? 0.78;
      persistLocal(next);
      api.savePreference(rankingKey, { weight: next.longTerm.stablePriorities[camel], source: 'confirmed' }).catch(() => undefined);
    } else {
      persistLocal(next);
      api.savePreference('shopping_style', { value: key === 'comparison_style' ? 'likes_comparing' : 'evidence_moves_to_action', source: 'confirmed' }).catch(() => undefined);
    }
  }

  function dismissInferredPreference(key: string) {
    const next = updateInferredPreference(context.profileSnapshot, key, 'rejected');
    persistLocal(next);
    api.savePreference(key, { value: 'dismissed', source: 'behavior_inferred', scope: 'observed' }).catch(() => undefined);
  }

  function updateConfirmedPreference(key: string, payload: { weight?: number; value?: unknown }) {
    const next = structuredClone(profile);
    if (key === 'budget_max' && typeof payload.value === 'number') {
      next.longTerm.usualBudgetRange = { max: payload.value };
    } else if (payload.weight != null) {
      next.longTerm.stablePriorities[key.includes('_') ? key.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase()) : key] = payload.weight;
    }
    next.lastUpdatedAt = new Date().toISOString();
    persistLocal(next);
    api.savePreference(rankingKeyFromClient(key), { ...payload, source: 'explicit' }).catch(() => undefined);
  }

  function removeConfirmedPreference(key: string) {
    const next = structuredClone(profile);
    if (key === 'budget_max') next.longTerm.usualBudgetRange = undefined;
    delete next.longTerm.stablePriorities[key];
    delete next.longTerm.stablePriorities[key.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase())];
    next.longTerm.shoppingStyle = (next.longTerm.shoppingStyle ?? []).filter((item) => item !== key);
    next.lastUpdatedAt = new Date().toISOString();
    persistLocal(next);
    api.deletePreference(rankingKeyFromClient(key)).catch(() => undefined);
  }

  function persistLocal(next: ShoppingDecisionProfile) {
    setProfile(next);
    writeJson(PROFILE_KEY, next);
    return next;
  }

  function getProduct(id: string | string[] | undefined) {
    const normalized = Array.isArray(id) ? id[0] : id;
    if (!normalized) return undefined;
    return products.find((product) => product.id === normalized) || productCache[normalized];
  }

  const ensureProduct = useCallback(async (id: string) => {
    const existing = products.find((product) => product.id === id) || productCache[id];
    if (existing?.reviews?.length) return existing;
    try {
      const item = humanizeProduct(await api.product(id));
      if (item.category !== 'Home Audio & Theater') return undefined;
      setProductCache((current) => ({ ...current, [id]: mergeCatalogProduct(current[id], item) }));
      setProducts((current) => current.map((product) => (product.id === id ? mergeCatalogProduct(product, item) : product)));
      return item;
    } catch {
      return existing;
    }
  }, [api, productCache, products]);

  const searchCatalog = useCallback(async (params: { q?: string; brand?: string; maxPrice?: number | null; sort?: string; offset?: number; limit?: number } = {}) => {
    const page = await api.products(params);
    const items = page.items.map(humanizeProduct).filter((item) => item.category === 'Home Audio & Theater');
    setProductCache((current) => {
      const next = { ...current };
      for (const item of items) next[item.id] = mergeCatalogProduct(current[item.id], item);
      return next;
    });
    return { items, count: page.count };
  }, [api]);

  useEffect(() => {
    if (conversationHydrating || !activeConversationId || !pickiMessages.length) return;
    const activeSummary = conversations.find((item) => item.id === activeConversationId);
    const timer = setTimeout(() => {
      if (activeConversationIdRef.current !== activeConversationId) return;
      const title = activeSummary?.manualTitle ? activeSummary.title : conversationTitle(pickiMessages);
      api.saveConversation(activeConversationId, title, {
        messages: pickiMessages,
        need,
        result,
        productId: quickTakeProductId,
        livePick,
        liveAlternatives,
        quickActions,
        changedSinceLastPick,
      }).then((saved) => {
        if (activeConversationIdRef.current !== activeConversationId) return;
        const row = saved as { title?: string; updatedAt?: string; state?: { manualTitle?: boolean } };
        setConversations((current) => [{ id: activeConversationId, title: row.title || title, updatedAt: row.updatedAt || new Date().toISOString(), contextProductId: quickTakeProductId, manualTitle: row.state?.manualTitle ?? activeSummary?.manualTitle }, ...current.filter((item) => item.id !== activeConversationId)]);
      }).catch(() => undefined);
    }, 450);
    return () => clearTimeout(timer);
  }, [activeConversationId, api, changedSinceLastPick, conversationHydrating, liveAlternatives, livePick, need, pickiMessages, quickActions, quickTakeProductId, result, conversations.find((item) => item.id === activeConversationId)?.manualTitle, conversations.find((item) => item.id === activeConversationId)?.title]);

  function resumeDecision() {
    setPickiOpen(true);
    if (!result.primaryRecommendation && need) {
      void runRecommendation(need).then((nextResult) => {
        setPickiMessages((current) => current.length ? current : [youMessage(need), replyFromFind(nextResult, need)]);
      });
    }
  }

  return (
    <StoreContext.Provider value={{ products, catalogCount, need, intent, result, compareIds, saved, events, profile, loadingProducts, runningDecision, conversationHydrating, error, runRecommendation, reloadProducts, openQuickTake, openPickiFind, closeQuickTake, followUpQuickTake, sendPickiMessage, pickiOpen, pickiWorkspaceActive, pickiMessages, pickiProductId, quickTakeProductId, quickTakeResult, quickTakeLoading, quickTakeError, decisionStatus, updateNeed, toggleCompare, track, saveCurrentDecision, confirmInferredPreference, dismissInferredPreference, updateConfirmedPreference, removeConfirmedPreference, getProduct, ensureProduct, searchCatalog, catalogBrands, resumeDecision, hasResumableDecision, conversations, activeConversationId, startNewConversation, openProductInPicki, renameConversation, deleteConversation, selectConversation, livePick, liveAlternatives, quickActions, changedSinceLastPick, memoryEvent, shoppingMemories, memoryEnabled, savedPicks, sendQuickAction, promoteAlternative, saveActivePick, forgetShoppingMemory, undoTasteSaved, saveShoppingPreference, confirmShoppingPreference, setShoppingPreferencePriority, dismissShoppingPreference, setMemoryEnabled, removeSavedPick, cart, cartSelected, addToCart, cartNotice, dismissCartNotice, removeFromCart, toggleCartSelected, setCartSelected, compareSelection, removeSelectedFromCart, comparisons, activeComparison, closeComparison, openComparison, askAboutComparison, keepComparisonPick, pendingComparison, relatedChats, relatedChatsForProducts, addTaste, confirmAgentAction, openFullChat, setPickiWorkspaceActive }}>
      {children}
    </StoreContext.Provider>
  );
}

function emptyResult(parsedIntent: UserIntent): RecommendationResult {
  return {
    id: 'not-started',
    parsedIntent,
    excludedProducts: [],
    primaryRecommendation: null,
    alternatives: [],
    regretGuard: '',
    evidenceSummary: '',
    missingInformation: [],
    dataUpdatedAt: '',
    trace: {
      profileSignalsUsed: [],
      inferredPreferencesUsed: [],
      confirmedPreferencesUsed: [],
      profileChangedRanking: false,
    },
  };
}

export function usePickMate() {
  const value = useContext(StoreContext);
  if (!value) throw new Error('usePickMate must be used inside PickMateProvider');
  return value;
}

function mergeCatalogProduct(existing: Product | undefined, incoming: Product): Product {
  if (!existing) return incoming;
  if ((incoming.reviews?.length ?? 0) > 0 || !(existing.reviews?.length)) return incoming;
  return {
    ...incoming,
    reviews: existing.reviews,
    discussions: existing.discussions.length ? existing.discussions : incoming.discussions,
    questions: existing.questions.length ? existing.questions : incoming.questions,
    videos: existing.videos.length ? existing.videos : incoming.videos,
    priceHistory: incoming.priceHistory.length ? incoming.priceHistory : existing.priceHistory,
    positiveThemes: incoming.positiveThemes.length ? incoming.positiveThemes : existing.positiveThemes,
    negativeThemes: incoming.negativeThemes.length ? incoming.negativeThemes : existing.negativeThemes,
  };
}

function humanizeSavedDecision(item: SavedDecision): SavedDecision {
  return {
    ...item,
    result: humanizeRecommendationResult(item.result),
  };
}
