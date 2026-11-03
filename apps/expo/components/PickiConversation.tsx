import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useResponsiveLayout } from './responsive';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { conversationInitialScrollTarget, conversationScrollOffset, rememberConversationScroll } from '../lib/conversationHistory';
import { conversationDisplayTitle } from '../lib/demo';
import { chatExamples } from '../lib/examples';
import { displayPrice, displayTitle } from '../lib/format';
import { isCableShoppingConversation, messageShowsGuidedActions, type PickiChatMessage } from '../lib/pickiTalk';
import type { Product } from '../types';
import { usePickMate } from '../store/PickMateStore';
import { colors, radius, spacing } from '../theme';
import { hasPickiStructuredExtras, PickiResponseView, pickiDisplayMessage } from './PickiResponseView';
import { PickiAvatar } from './PickiAvatar';
import { ProductVisual } from './ProductVisual';

export function PickiConversation({
  mode = 'page',
  onClose,
  onOpenChats,
  embedded = false,
  showHeader = true,
  sheet = false,
}: {
  mode?: 'page' | 'drawer';
  onClose?: () => void;
  onOpenChats?: () => void;
  embedded?: boolean;
  showHeader?: boolean;
  sheet?: boolean;
}) {
  const layout = useResponsiveLayout();
  const insets = useSafeAreaInsets();
  const {
    pickiMessages,
    pickiProductId,
    runningDecision,
    conversationHydrating,
    decisionStatus,
    quickActions,
    quickTakeLoading,
    sendPickiMessage,
    sendQuickAction,
    getProduct,
    memoryEvent,
    forgetShoppingMemory,
    cart,
    activeConversationId,
    addToCart,
    compareSelection,
    cartSelected,
    pendingComparison,
    startNewConversation,
    openFullChat,
    conversations,
    confirmAgentAction,
  } = usePickMate();
  const [draft, setDraft] = useState('');
  const scroller = useRef<ScrollView>(null);
  const scrollPositions = useRef<Record<string, number>>({});
  const activeScrollId = useRef<string | null>(activeConversationId);
  const currentScrollOffset = useRef(0);
  const pendingScrollRestore = useRef<number | null>(null);
  const messageCounts = useRef<Record<string, number>>({});
  const busy = runningDecision || quickTakeLoading || conversationHydrating;
  const chat = conversations.find((item) => item.id === activeConversationId);
  const contextProduct = pickiProductId ? cartProduct(pickiMessages, pickiProductId) || getProduct(pickiProductId) : undefined;
  const contextName = contextProduct ? displayTitle(contextProduct) : '';
  const cableConversation = isCableShoppingConversation(pickiMessages);
  const latestPicki = [...pickiMessages].reverse().find((item) => item.from === 'picki');
  const hasInlineActions = Boolean(latestPicki?.structured?.suggestedActions?.length || latestPicki?.structured?.clarificationOptions?.length);

  useEffect(() => {
    scrollPositions.current = rememberConversationScroll(
      scrollPositions.current,
      activeScrollId.current,
      currentScrollOffset.current,
    );
    activeScrollId.current = activeConversationId;
    currentScrollOffset.current = conversationScrollOffset(scrollPositions.current, activeConversationId);
    pendingScrollRestore.current = activeConversationId
      ? activeConversationId in scrollPositions.current ? currentScrollOffset.current : -1
      : null;
  }, [activeConversationId]);

  useEffect(() => {
    if (!activeConversationId) return;
    const previousCount = messageCounts.current[activeConversationId];
    messageCounts.current[activeConversationId] = pickiMessages.length;
    if (previousCount != null && pickiMessages.length > previousCount) {
      scroller.current?.scrollToEnd({ animated: true });
    }
  }, [activeConversationId, pickiMessages]);

  function send() {
    const value = draft.trim();
    if (!value || busy) return;
    setDraft('');
    void sendPickiMessage(value);
  }

  function openProduct(id: string) {
    onClose?.();
    openFullChat();
    router.push(`/product/${id}${activeConversationId ? `?from=${encodeURIComponent(activeConversationId)}` : ''}`);
  }

  const composerBottom = sheet
    ? 8
    : embedded
      ? 10
      : Math.max(10, insets.bottom);

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={0}
      style={[styles.root, sheet && styles.rootSheet]}
    >
      {showHeader ? (
        <View style={styles.header}>
          <PickiAvatar />
          <View style={styles.headerCopy}>
            <View style={styles.nameRow}>
              <Text style={[styles.name, layout.isMobile && styles.nameMobile]}>Picki</Text>
              <View style={styles.onlineDot} />
            </View>
            <Text style={[styles.role, layout.isMobile && styles.roleMobile]} numberOfLines={1}>{chat ? conversationDisplayTitle(chat) : 'Your shopping decision assistant'}</Text>
          </View>
          {mode === 'drawer' ? (
            <Pressable onPress={() => { openFullChat(); onClose?.(); router.push('/'); }} style={styles.headerButton}>
              <Text style={styles.headerButtonText}>Open workspace</Text>
            </Pressable>
          ) : !embedded ? (
            <Pressable accessibilityState={{ disabled: busy }} disabled={busy} onPress={() => { void startNewConversation(); }} style={[styles.headerButton, busy && { opacity: 0.45 }]}>
              <Text style={styles.headerButtonText}>New conversation</Text>
            </Pressable>
          ) : null}
          {onOpenChats ? (
            <Pressable accessibilityRole="button" onPress={onOpenChats} style={styles.close}>
              <Text style={[styles.closeText, layout.isMobile && styles.closeTextMobile]}>Chats</Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}

      <ScrollView
        ref={scroller}
        style={styles.thread}
        contentContainerStyle={[styles.threadBody, sheet && styles.threadBodySheet]}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode={Platform.OS === 'ios' ? 'interactive' : 'on-drag'}
        scrollEventThrottle={16}
        onScroll={(event) => {
          currentScrollOffset.current = event.nativeEvent.contentOffset.y;
        }}
        onContentSizeChange={() => {
          if (pendingScrollRestore.current === -1) {
            if (conversationInitialScrollTarget(pickiMessages.length) === 'end') {
              scroller.current?.scrollToEnd({ animated: false });
            } else {
              scroller.current?.scrollTo({ y: 0, animated: false });
            }
            pendingScrollRestore.current = null;
          } else if (pendingScrollRestore.current != null) {
            scroller.current?.scrollTo({ y: pendingScrollRestore.current, animated: false });
            pendingScrollRestore.current = null;
          }
        }}
      >
        {pickiProductId && !sheet ? (
          <View style={styles.contextPill}>
            <Text style={styles.contextText}>Analyzing: <Text style={styles.contextStrong}>{contextName || 'this product'}</Text></Text>
          </View>
        ) : null}
        {pendingComparison ? (
          <View style={styles.contextPill}>
            <Text style={styles.contextText}>Your selected products are ready. Sending a question will save this as a separate conversation.</Text>
          </View>
        ) : null}
        {!pickiMessages.length && !busy ? (
          <EmptyChat
            onStart={(prompt) => { void sendPickiMessage(prompt); }}
            compact={sheet || layout.isMobile}
            mobile={layout.isMobile}
          />
        ) : null}
        {pickiMessages.map((line) => (
          <ChatBubble
            key={line.id}
            message={line}
            hideProductId={mode === 'drawer' ? pickiProductId : null}
            cartIds={cart.map((item) => item.productId)}
            onOpenProduct={openProduct}
            onAdd={(id) => addToCart(id, { conversationId: activeConversationId, sourceType: 'chat' })}
            onConfirmAction={(action) => confirmAgentAction(action)}
            getProduct={getProduct}
            onQuickAction={(action) => { void sendQuickAction(action); }}
            onSendMessage={(text) => { void sendPickiMessage(text); }}
            showGuidedActions={messageShowsGuidedActions(line.id, latestPicki?.id)}
            compact={sheet || layout.isNarrowPhone}
            mobile={layout.isMobile}
          />
        ))}
        {busy ? (
          <View style={styles.pickiRow}>
            <PickiAvatar tiny />
            <View style={styles.pickiBubble}>
              <ActivityIndicator color={colors.brand} />
              <Text style={[styles.thinking, layout.isMobile && styles.thinkingMobile]}>{decisionStatus || 'Checking the catalog and available evidence…'}</Text>
            </View>
          </View>
        ) : null}
      </ScrollView>

      {memoryEvent ? (
        <View style={styles.remembered}>
          <Text style={styles.rememberedText}>Picki remembered: {memoryEvent.label}</Text>
          <Pressable onPress={() => forgetShoppingMemory(memoryEvent.id)}><Text style={styles.undo}>Undo</Text></Pressable>
        </View>
      ) : null}
      {!hasInlineActions && quickActions.length && sheet ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.quickiesScroll} contentContainerStyle={[styles.quickies, styles.quickiesSheet]}>
          <QuickActions mobile={layout.isMobile} actions={quickActions} busy={busy} cartLength={cart.length} showAlternative={!cableConversation} onCheaper={() => sendQuickAction('cheaper')} onStyle={() => sendQuickAction('different_style')} onWhy={() => sendQuickAction('why_this')} onCompare={() => {
            if (cartSelected.length >= 2 && cartSelected.length <= 4) void compareSelection();
            else router.push('/saved');
          }} />
        </ScrollView>
      ) : !hasInlineActions && quickActions.length ? (
        <View style={styles.quickies}>
          <QuickActions mobile={layout.isMobile} actions={quickActions} busy={busy} cartLength={cart.length} showAlternative={!cableConversation} onCheaper={() => sendQuickAction('cheaper')} onStyle={() => sendQuickAction('different_style')} onWhy={() => sendQuickAction('why_this')} onCompare={() => {
            if (cartSelected.length >= 2 && cartSelected.length <= 4) void compareSelection();
            else router.push('/saved');
          }} />
        </View>
      ) : null}
      <View style={[styles.composer, sheet && styles.composerSheet, { paddingBottom: composerBottom }]}>
        <TextInput
          value={draft}
          onChangeText={setDraft}
          placeholder="Ask Picki a follow-up…"
          placeholderTextColor={colors.textSoft}
          style={[styles.input, layout.isMobile && styles.inputMobile]}
          multiline
        />
        <Pressable accessibilityLabel="Send message" disabled={!draft.trim() || busy} onPress={send} style={[styles.send, (!draft.trim() || busy) && styles.disabled]}>
          <Ionicons name="arrow-up" size={19} color={colors.white} />
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

function EmptyChat({ onStart, compact, mobile }: { onStart: (prompt: string) => void; compact?: boolean; mobile?: boolean }) {
  return (
    <View style={[styles.empty, compact && styles.emptyCompact]}>
      <Text style={[styles.emptyTitle, compact && styles.emptyTitleCompact, mobile && styles.emptyTitleMobile]}>
        What are you shopping for?
      </Text>
      <View style={[styles.starterWrap, compact && styles.starterWrapCompact]}>
        {chatExamples.map((example) => (
          <Pressable
            accessibilityLabel={example.label}
            key={example.prompt}
            onPress={() => onStart(example.prompt)}
            style={[styles.starter, compact && styles.starterCompact]}
          >
            <Text style={[styles.starterTitle, mobile && styles.starterTitleMobile]}>{example.label}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function ChatBubble({
  message,
  hideProductId,
  cartIds,
  onOpenProduct,
  onAdd,
  onConfirmAction,
  getProduct,
  onQuickAction,
  onSendMessage,
  showGuidedActions,
  compact,
  mobile,
}: {
  message: PickiChatMessage;
  hideProductId: string | null;
  cartIds: string[];
  onOpenProduct: (id: string) => void;
  onAdd: (id: string) => void;
  onConfirmAction: (action: { type: 'cart_update' | 'preference_update'; payload: Record<string, unknown> }) => Promise<{ ok: boolean; message: string }>;
  getProduct: (id: string) => Product | undefined;
  onQuickAction: (action: 'cheaper' | 'compare' | 'why_this') => void;
  onSendMessage: (text: string) => void;
  showGuidedActions: boolean;
  compact?: boolean;
  mobile?: boolean;
}) {
  if (message.from === 'you') {
    return (
      <View style={styles.youRow}>
        <View style={styles.youBubble}>
          <Text style={[styles.youText, mobile && styles.youTextMobile]}>{message.text}</Text>
        </View>
      </View>
    );
  }
  const products = (message.products?.length ? message.products : message.product ? [message.product] : []).filter((item) => item.id !== hideProductId);
  const structured = message.structured;
  const presentedStructured = structured && !showGuidedActions
    ? { ...structured, suggestedActions: [], clarificationOptions: [] }
    : structured;
  const richExtras = hasPickiStructuredExtras(structured);
  const leadText = pickiDisplayMessage(message.text, structured);
  return (
    <View style={styles.pickiRow}>
      <PickiAvatar tiny />
      <View style={[styles.pickiCol, richExtras && styles.pickiColRich]}>
        <View style={[styles.pickiBubble, richExtras && styles.pickiBubbleRich]}>
          <Text style={[styles.pickiText, mobile && styles.pickiTextMobile, richExtras && styles.pickiLead, richExtras && mobile && styles.pickiLeadMobile]}>{leadText}</Text>
          {structured && richExtras ? (
            <PickiResponseView
              structured={presentedStructured ?? structured}
              getProduct={getProduct}
              onQuickAction={onQuickAction}
              onSendMessage={onSendMessage}
              onOpenProduct={onOpenProduct}
              onSaveProduct={onAdd}
              savedProductIds={cartIds}
            />
          ) : null}
        </View>
        {(message.proposedActions ?? []).map((action) => (
          <Pressable
            key={action.id}
            onPress={() => { void onConfirmAction({ type: action.type, payload: action.payload }).then((result) => {
              if (result.ok) return;
            }); }}
            style={styles.proposedAction}
          >
            <Text style={styles.proposedActionText}>Confirm action: {action.summary}</Text>
          </Pressable>
        ))}
        {!structured?.productRefs?.length ? products.map((product) => (
          <PickCard
            key={product.id}
            product={product}
            inCart={cartIds.includes(product.id)}
            onOpen={() => onOpenProduct(product.id)}
            onAdd={() => onAdd(product.id)}
            compact={compact}
            mobile={mobile}
          />
        )) : null}
      </View>
    </View>
  );
}

function PickCard({ product, inCart, onOpen, onAdd, compact, mobile }: { product: Product; inCart: boolean; onOpen: () => void; onAdd: () => void; compact?: boolean; mobile?: boolean }) {
  return (
    <View style={styles.pick}>
      <View style={[styles.pickMain, compact && styles.pickMainCompact]}>
        <View style={[styles.thumb, compact && styles.thumbCompact]}><ProductVisual product={product} size={compact ? 72 : 84} /></View>
        <View style={styles.pickCopy}>
          {product.brand ? <Text style={[styles.brand, mobile && styles.brandMobile]}>{product.brand}</Text> : null}
          <Text style={[styles.pickName, mobile && styles.pickNameMobile]} numberOfLines={compact ? undefined : 2}>{displayTitle(product)}</Text>
          <Text style={[styles.price, mobile && styles.priceMobile]}>{displayPrice(product)}</Text>
          <View style={styles.pickActions}>
            <Pressable onPress={inCart ? () => router.push('/saved') : onAdd} style={styles.cardButton}><Text style={[styles.cardButtonText, mobile && styles.cardButtonTextMobile]}>{inCart ? 'View My Picks' : 'Save to My Picks'}</Text></Pressable>
            <Pressable onPress={onOpen} style={styles.cardButtonMuted}><Text style={[styles.cardButtonMutedText, mobile && styles.cardButtonTextMobile]}>View product</Text></Pressable>
          </View>
        </View>
      </View>
    </View>
  );
}

function QuickActions({
  mobile,
  actions,
  busy,
  cartLength,
  showAlternative,
  onCheaper,
  onStyle,
  onWhy,
  onCompare,
}: {
  mobile?: boolean;
  actions: Array<'cheaper' | 'different_style' | 'compare' | 'why_this'>;
  busy: boolean;
  cartLength: number;
  showAlternative: boolean;
  onCheaper: () => void;
  onStyle: () => void;
  onWhy: () => void;
  onCompare: () => void;
}) {
  return (
    <>
      {actions.includes('cheaper') ? <Pressable disabled={busy} onPress={onCheaper} style={styles.quick}><Text style={[styles.quickText, mobile && styles.quickTextMobile]}>Find a cheaper option</Text></Pressable> : null}
      {showAlternative && actions.includes('different_style') ? <Pressable disabled={busy} onPress={onStyle} style={styles.quick}><Text style={[styles.quickText, mobile && styles.quickTextMobile]}>Try a different approach</Text></Pressable> : null}
      {actions.includes('why_this') ? <Pressable disabled={busy} onPress={onWhy} style={styles.quick}><Text style={[styles.quickText, mobile && styles.quickTextMobile]}>Why this one?</Text></Pressable> : null}
      {actions.includes('compare') || cartLength > 1 ? (
        <Pressable disabled={busy} onPress={onCompare} style={styles.quick}>
          <Text style={[styles.quickText, mobile && styles.quickTextMobile]}>Compare My Picks</Text>
        </Pressable>
      ) : null}
    </>
  );
}

function cartProduct(messages: PickiChatMessage[], id: string) {
  for (const message of messages) {
    const found = message.products?.find((item) => item.id === id) || (message.product?.id === id ? message.product : undefined);
    if (found) return found;
  }
  return undefined;
}

const styles = StyleSheet.create({
  root: { flex: 1, minHeight: 0, backgroundColor: colors.white },
  rootSheet: { width: '100%' },
  header: { minHeight: 66, flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: spacing.lg, paddingVertical: 11, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border, backgroundColor: 'rgba(255,255,255,0.96)' },
  headerCopy: { flex: 1, minWidth: 0 },
  nameRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  name: { color: colors.textPrimary, fontSize: 16, fontWeight: '900', letterSpacing: -0.2 },
  nameMobile: { fontSize: 15 },
  onlineDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.success },
  role: { color: colors.textSoft, fontSize: 11, marginTop: 1 },
  roleMobile: { fontSize: 10 },
  headerButton: { flexShrink: 0, borderRadius: 10, borderWidth: 1, borderColor: '#E7E5E2', backgroundColor: colors.white, paddingVertical: 7, paddingHorizontal: 10 },
  headerButtonText: { color: colors.textPrimary, fontSize: 12, fontWeight: '700' },
  close: { paddingVertical: 6, paddingHorizontal: 4 },
  closeText: { color: colors.brand, fontSize: 13, fontWeight: '700' },
  closeTextMobile: { fontSize: 12 },
  contextPill: { alignSelf: 'flex-start', backgroundColor: '#FFF8F3', borderWidth: 1, borderColor: '#FFE6D6', borderRadius: 10, paddingVertical: 8, paddingHorizontal: 11 },
  contextText: { color: '#71594D', fontSize: 11 },
  contextStrong: { fontWeight: '800' },
  empty: { alignItems: 'flex-start', gap: 12, paddingTop: 8 },
  emptyCompact: { gap: 10, paddingTop: 4 },
  emptyTitle: { color: colors.textPrimary, fontSize: 26, lineHeight: 32, fontWeight: '800', letterSpacing: -0.5 },
  emptyTitleCompact: { fontSize: 22, lineHeight: 28 },
  emptyTitleMobile: { fontSize: 20, lineHeight: 25 },
  starterWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, width: '100%' },
  starterWrapCompact: { flexDirection: 'column', gap: 8 },
  starter: { minWidth: 0, minHeight: 58, flexGrow: 1, flexBasis: '30%', justifyContent: 'center', borderRadius: 12, borderWidth: 1, borderColor: '#EEEAE7', backgroundColor: colors.white, paddingVertical: 12, paddingHorizontal: 14 },
  starterCompact: { width: '100%', minHeight: 52, flexBasis: 'auto', flexGrow: 0, paddingVertical: 10, paddingHorizontal: 12 },
  starterTitle: { color: '#272321', fontSize: 15, lineHeight: 21, fontWeight: '800' },
  starterTitleMobile: { fontSize: 14, lineHeight: 19 },
  thread: { flex: 1, minHeight: 0 },
  threadBody: { paddingHorizontal: spacing.xl, paddingTop: spacing.xl, gap: 16, paddingBottom: 24, maxWidth: 1120, width: '100%', alignSelf: 'center' },
  threadBodySheet: { paddingHorizontal: spacing.md, paddingTop: spacing.md, maxWidth: '100%', alignSelf: 'stretch' },
  youRow: { alignItems: 'flex-end' },
  youBubble: { maxWidth: '82%', borderRadius: 18, borderBottomRightRadius: 6, backgroundColor: '#FFF1E8', paddingVertical: 11, paddingHorizontal: 15 },
  youText: { color: colors.textPrimary, fontSize: 16, lineHeight: 23 },
  youTextMobile: { fontSize: 14, lineHeight: 20 },
  pickiRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  pickiCol: { flex: 1, minWidth: 0, gap: 8, maxWidth: 760 },
  pickiColRich: { maxWidth: 1050 },
  pickiBubble: { borderRadius: 16, borderBottomLeftRadius: 5, backgroundColor: '#F7F6F4', paddingVertical: 11, paddingHorizontal: 15, gap: 6 },
  pickiBubbleRich: { borderRadius: 18, borderBottomLeftRadius: 6, backgroundColor: colors.white, borderWidth: 1, borderColor: '#EAE6E1', paddingVertical: 16, paddingHorizontal: 16 },
  pickiText: { color: '#3D3834', fontSize: 16, lineHeight: 23 },
  pickiTextMobile: { fontSize: 14, lineHeight: 20 },
  pickiLead: { color: colors.textPrimary, fontSize: 17, lineHeight: 25, fontWeight: '500', letterSpacing: -0.1 },
  pickiLeadMobile: { fontSize: 15, lineHeight: 21 },
  proposedAction: { borderRadius: 10, borderWidth: 1, borderColor: colors.brand, paddingVertical: 8, paddingHorizontal: 10, backgroundColor: colors.brandSoft },
  proposedActionText: { color: colors.brandInk, fontSize: 12, fontWeight: '700' },
  thinking: { color: colors.textSecondary, fontSize: 13 },
  thinkingMobile: { fontSize: 12 },
  pick: { borderWidth: 1, borderColor: colors.border, borderRadius: 14, padding: 12, backgroundColor: colors.white },
  pickMain: { flexDirection: 'row', gap: 12 },
  pickMainCompact: { flexDirection: 'column' },
  thumb: { width: 94, height: 84, borderRadius: radius.sm, overflow: 'hidden', backgroundColor: '#F8F8F7' },
  thumbCompact: { width: '100%', height: 120 },
  pickCopy: { flex: 1, minWidth: 0, gap: 2 },
  brand: { color: colors.textSoft, fontSize: 10, fontWeight: '800', letterSpacing: 1, textTransform: 'uppercase' },
  brandMobile: { fontSize: 9 },
  pickName: { color: colors.textPrimary, fontSize: 13, fontWeight: '800', lineHeight: 18 },
  pickNameMobile: { fontSize: 12, lineHeight: 16 },
  price: { color: colors.brand, fontSize: 15, fontWeight: '800', marginTop: 4 },
  priceMobile: { fontSize: 14 },
  pickActions: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8 },
  cardButton: { borderRadius: 8, backgroundColor: colors.brand, paddingVertical: 6, paddingHorizontal: 8 },
  cardButtonText: { color: colors.white, fontSize: 11, fontWeight: '800' },
  cardButtonMuted: { borderRadius: 8, borderWidth: 1, borderColor: '#E7E5E2', paddingVertical: 6, paddingHorizontal: 8 },
  cardButtonMutedText: { color: colors.textPrimary, fontSize: 11, fontWeight: '700' },
  cardButtonTextMobile: { fontSize: 10 },
  remembered: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginHorizontal: spacing.lg, marginTop: 8, padding: 10, borderRadius: radius.md, backgroundColor: '#FFF4ED' },
  rememberedText: { flex: 1, color: colors.brandInk, fontSize: 12, fontWeight: '700' },
  undo: { color: colors.brand, fontSize: 12, fontWeight: '800' },
  quickiesScroll: { flexGrow: 0, maxHeight: 50 },
  quickies: { flexDirection: 'row', flexWrap: 'wrap', gap: 7, width: '100%', maxWidth: 960, alignSelf: 'center', paddingHorizontal: spacing.xl, paddingTop: 8 },
  quickiesSheet: { flexWrap: 'nowrap', paddingHorizontal: spacing.md, paddingTop: 8, paddingBottom: 2 },
  quick: { borderRadius: radius.round, borderWidth: 1, borderColor: '#ECE8E4', backgroundColor: colors.white, paddingVertical: 8, paddingHorizontal: 12 },
  quickText: { color: '#625950', fontSize: 11, fontWeight: '800' },
  quickTextMobile: { fontSize: 10 },
  composer: { width: '92%', maxWidth: 920, alignSelf: 'center', flexDirection: 'row', alignItems: 'flex-end', gap: 8, marginTop: 9, marginBottom: 4, borderRadius: 18, borderWidth: 1, borderColor: '#E6E1DC', backgroundColor: colors.white, paddingLeft: 16, paddingRight: 7, paddingVertical: 7 },
  composerSheet: { marginHorizontal: spacing.md, marginTop: 6 },
  input: { flex: 1, minHeight: 38, maxHeight: 105, color: colors.textPrimary, fontSize: 14, lineHeight: 20, paddingVertical: 9 },
  inputMobile: { fontSize: 13, lineHeight: 18 },
  send: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center', borderRadius: 13, backgroundColor: colors.brand },
  disabled: { opacity: 0.45 },
});
