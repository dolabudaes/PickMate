import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { StructuredPickiResponse, SuggestedPickiAction } from '../lib/shoppingTurn';
import { displayPrice, displayTitle } from '../lib/format';
import type { Product } from '../types';
import { colors, radius } from '../theme';
import { groupRecommendationRefs, shouldUseRecommendationCards, structuredComparisonLayout, visibleSuggestedActions } from '../lib/recommendationPresentation';
import { humanizeText } from '../lib/presentation';
import { PickiDecisionBrief } from './PickiDecisionBrief';
import { ProductVisual } from './ProductVisual';
import { useResponsiveLayout } from './responsive';

export function pickiDisplayMessage(text: string, structured?: StructuredPickiResponse | null) {
  if (structured?.primaryMessage?.trim()) return humanizeText(structured.primaryMessage.trim());
  return humanizeText(text);
}

export function hasPickiStructuredExtras(structured?: StructuredPickiResponse | null) {
  if (!structured) return false;
  return Boolean(
    structured.keyFacts?.length
    || structured.productRefs?.length
    || structured.detailSections?.length
    || structured.suggestedActions?.length
    || structured.clarificationOptions?.length
    || structured.comparisonData?.rows?.length
    ||     structured.decisionHighlight
    || structured.decisionBrief,
  );
}

export function PickiResponseView({
  structured,
  getProduct,
  onQuickAction,
  onSendMessage,
  onOpenProduct,
  onSaveProduct,
  savedProductIds,
}: {
  structured: StructuredPickiResponse;
  getProduct: (id: string) => Product | undefined;
  onQuickAction: (action: 'cheaper' | 'compare' | 'why_this') => void;
  onSendMessage: (text: string) => void;
  onOpenProduct?: (id: string) => void;
  onSaveProduct?: (id: string) => void;
  savedProductIds?: string[];
}) {
  const layout = useResponsiveLayout();
  const comparisonLayout = structuredComparisonLayout(layout.isMobile);
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({});
  const comparison = structured.comparisonData;
  const mobilePair = layout.isMobile && comparison?.columns?.length === 2;
  const recommendationRefs = groupRecommendationRefs(structured.productRefs);
  const showRecommendationCards = shouldUseRecommendationCards(structured);
  if (structured.decisionBrief) {
    return (
      <View style={styles.wrap}>
        {showRecommendationCards && recommendationRefs.primary ? (
          <RecommendationCards
            structured={structured}
            refs={recommendationRefs}
            getProduct={getProduct}
            onOpenProduct={onOpenProduct}
          />
        ) : null}
        <PickiDecisionBrief
          structured={showRecommendationCards ? { ...structured, productRefs: [] } : structured}
          getProduct={getProduct}
          onSendMessage={onSendMessage}
        />
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      {structured.decisionHighlight ? (
        <View style={styles.decision}>
          <Text style={[styles.decisionText, layout.isMobile && styles.decisionTextMobile]}>{structured.decisionHighlight}</Text>
        </View>
      ) : null}

      {structured.clarificationOptions?.length ? (
        <View style={styles.actions}>
          {visibleSuggestedActions(structured.clarificationOptions).map((option) => (
            <Pressable
              key={option.id || option.label}
              onPress={() => onSendMessage(option.message)}
              style={styles.actionChip}
            >
              <Text style={[styles.actionText, layout.isMobile && styles.actionTextMobile]}>{option.label}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}

      {comparison?.columns?.length ? (
        <View style={styles.compare}>
          <View style={[styles.compareCards, comparisonLayout.direction === 'row' ? styles.compareCardsDesktop : styles.compareCardsMobile, mobilePair && styles.compareCardsMobilePair]}>
            {(comparison.columns || []).slice(0, 3).map((column, columnIndex) => {
              const product = column.productId ? getProduct(column.productId) : undefined;
              const productRef = structured.productRefs?.find((item) => item.productId === column.productId);
              const isSaved = Boolean(column.productId && savedProductIds?.includes(column.productId));
              return (
                <View
                  key={column.productId || column.title}
                  style={[styles.compareCard, comparisonLayout.cardWidth === 'auto' ? styles.compareCardDesktop : styles.compareCardMobile, mobilePair && styles.compareCardMobilePair]}
                >
                  {productRef?.badge ? <Text style={[comparison.winnerProductId === column.productId || productRef.role === 'primary' ? styles.matchBadge : styles.matchBadgeMuted, layout.isMobile && styles.matchBadgeMobile]}>{productRef.badge}</Text> : comparison.winnerProductId === column.productId ? <Text style={[styles.matchBadge, layout.isMobile && styles.matchBadgeMobile]}>Best fit</Text> : null}
                  <Pressable onPress={() => column.productId && (onOpenProduct ? onOpenProduct(column.productId) : router.push(`/product/${column.productId}`))}>
                    {product ? <View style={[styles.compareThumb, mobilePair && styles.compareThumbMobilePair]}><ProductVisual product={product} size={mobilePair ? 76 : 96} /></View> : <View style={[styles.compareThumb, mobilePair && styles.compareThumbMobilePair]} />}
                    <Text style={[styles.compareTitle, layout.isMobile && styles.compareTitleMobile]} numberOfLines={mobilePair ? 3 : comparisonLayout.truncateText ? 2 : undefined}>{product ? displayTitle(product) : column.title || 'Product'}</Text>
                    <Text style={[styles.comparePrice, layout.isMobile && styles.comparePriceMobile]}>{column.price != null ? `$${column.price.toFixed(2)}` : 'Price unavailable'}</Text>
                  </Pressable>
                  <View style={styles.cardFacts}>
                    {(comparison.rows || []).slice(0, 4).map((row) => (
                      <View key={`${column.productId}-${row.label}`} style={styles.cardFact}>
                        <Text style={[styles.cardFactLabel, layout.isMobile && styles.cardFactLabelMobile]}>{comparisonLabel(row.label)}</Text>
                        <Text style={[styles.cardFactValue, layout.isMobile && styles.cardFactValueMobile]}>{row.values[columnIndex] || 'Not verified'}</Text>
                      </View>
                    ))}
                  </View>
                  <View style={styles.cardButtons}>
                    <Pressable
                      accessibilityLabel={isSaved ? 'View in My Picks' : 'Save to My Picks'}
                      onPress={() => isSaved ? router.push('/saved') : column.productId && onSaveProduct?.(column.productId)}
                      style={[styles.saveButton, isSaved && styles.saveButtonSaved]}
                    >
                      {isSaved ? <Ionicons name="checkmark-circle" size={14} color={colors.success} accessibilityElementsHidden /> : null}
                      <Text style={[styles.saveButtonText, layout.isMobile && styles.buttonTextMobile, isSaved && styles.saveButtonTextSaved]}>{isSaved ? 'Already in My Picks' : 'Save to My Picks'}</Text>
                    </Pressable>
                    <Pressable onPress={() => column.productId && (onOpenProduct ? onOpenProduct(column.productId) : router.push(`/product/${column.productId}`))} style={styles.openButton}><Text style={[styles.openButtonText, layout.isMobile && styles.buttonTextMobile]}>View product</Text></Pressable>
                  </View>
                </View>
              );
            })}
          </View>
        </View>
      ) : null}

      {!comparison?.columns?.length && showRecommendationCards && recommendationRefs.primary ? (
        <RecommendationCards
          structured={structured}
          refs={recommendationRefs}
          getProduct={getProduct}
          onOpenProduct={onOpenProduct}
        />
      ) : !comparison?.columns?.length && structured.productRefs?.length ? (
        <View style={styles.refs}>
          {structured.productRefs.map((ref) => {
            const product = ref.productId ? getProduct(ref.productId) : undefined;
            return (
              <Pressable
                key={`${ref.productId}-${ref.role}`}
                style={styles.refRow}
                onPress={() => ref.productId && (onOpenProduct ? onOpenProduct(ref.productId) : router.push(`/product/${ref.productId}`))}
              >
                <View style={styles.refThumb}>
                  {product ? <ProductVisual product={product} size={76} /> : <View style={styles.refPlaceholder} />}
                </View>
                <View style={styles.refCopy}>
                  {ref.badge || (ref.role === 'primary' && structured.responseType === 'RECOMMENDATION' && !structured.decisionHighlight) ? <Text style={[styles.refEyebrow, layout.isMobile && styles.refEyebrowMobile]}>{ref.badge || 'PICKI PICK'}</Text> : null}
                  <Text style={[styles.refTitle, layout.isMobile && styles.refTitleMobile]} numberOfLines={layout.isMobile ? undefined : 2}>{product ? displayTitle(product) : ref.title || 'Product'}</Text>
                  {ref.price != null ? <Text style={[styles.refPrice, layout.isMobile && styles.refPriceMobile]}>${ref.price.toFixed(2)}</Text> : product ? <Text style={[styles.refPrice, layout.isMobile && styles.refPriceMobile]}>{displayPrice(product)}</Text> : null}
                  {ref.specLine ? <Text style={[styles.refSpec, layout.isMobile && styles.refSpecMobile]} numberOfLines={layout.isMobile ? undefined : 1}>{ref.specLine}</Text> : null}
                </View>
              </Pressable>
            );
          })}
        </View>
      ) : null}

      {structured.detailSections?.map((section) => {
        const expanded = openSections[section.id] ?? !section.collapsed;
        if (!section.lines?.length) return null;
        return (
          <View key={section.id} style={styles.detailBlock}>
            <Pressable
              onPress={() => setOpenSections((current) => ({ ...current, [section.id]: !expanded }))}
              style={styles.detailToggle}
            >
              <Text style={[styles.detailLabel, layout.isMobile && styles.detailLabelMobile]}>{expanded ? 'Hide ' : 'View '}{section.title}</Text>
            </Pressable>
            {expanded ? (
              <View style={styles.detailLines}>
                {section.lines.map((line) => (
                  <Text key={`${section.id}-${line}`} style={[styles.detailLine, layout.isMobile && styles.detailLineMobile]}>{line}</Text>
                ))}
              </View>
            ) : null}
          </View>
        );
      })}

      {!structured.clarificationOptions?.length && structured.suggestedActions?.length ? (
        <View style={styles.actions}>
          {visibleSuggestedActions(structured.suggestedActions).map((action) => (
            <Pressable
              key={action.id}
              onPress={() => runSuggestedAction(action, onQuickAction, onSendMessage)}
              style={styles.actionChip}
            >
              <Text style={[styles.actionText, layout.isMobile && styles.actionTextMobile]}>{action.label}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function RecommendationCards({
  structured,
  refs,
  getProduct,
  onOpenProduct,
}: {
  structured: StructuredPickiResponse;
  refs: ReturnType<typeof groupRecommendationRefs>;
  getProduct: (id: string) => Product | undefined;
  onOpenProduct?: (id: string) => void;
}) {
  const layout = useResponsiveLayout();
  const ref = refs.primary;
  if (!ref) return null;
  const product = ref.productId ? getProduct(ref.productId) : undefined;
  const title = product ? displayTitle(product) : ref.title || 'Recommended product';

  return (
    <View style={styles.recommendations}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`View recommended product: ${title}`}
        style={styles.primaryCard}
        onPress={() => ref.productId && (onOpenProduct ? onOpenProduct(ref.productId) : router.push(`/product/${ref.productId}`))}
      >
        <View style={styles.primaryLabelRow}>
          <View style={styles.primaryBadge}>
            <Ionicons name="sparkles" size={12} color={colors.brandInk} accessibilityElementsHidden />
            <Text style={[styles.primaryBadgeText, layout.isMobile && styles.primaryBadgeTextMobile]}>{ref.badge || 'BEST MATCH'}</Text>
          </View>
          {structured.evidenceStatus ? (
            <Text style={[styles.evidenceStatus, layout.isMobile && styles.evidenceStatusMobile]}>{structured.evidenceStatus === 'catalog' ? 'Catalog verified' : structured.evidenceStatus === 'verified_reviews' ? 'Reviews verified' : 'Limited evidence'}</Text>
          ) : null}
        </View>
        <View style={styles.primaryMain}>
          <View style={styles.primaryThumb}>
            {product ? <ProductVisual product={product} size={104} /> : <View style={styles.refPlaceholder} />}
          </View>
          <View style={styles.primaryCopy}>
            {ref.brand || product?.brand ? <Text style={[styles.primaryBrand, layout.isMobile && styles.primaryBrandMobile]}>{ref.brand || product?.brand}</Text> : null}
            <Text style={[styles.primaryTitle, layout.isMobile && styles.primaryTitleMobile]}>{title}</Text>
            <Text style={[styles.primaryPrice, layout.isMobile && styles.primaryPriceMobile]}>{ref.price != null ? `$${ref.price.toFixed(2)}` : product ? displayPrice(product) : 'Price unavailable'}</Text>
            {ref.specLine ? <Text style={[styles.primarySpec, layout.isMobile && styles.primarySpecMobile]}>{ref.specLine}</Text> : null}
          </View>
        </View>
        {structured.keyFacts?.length ? (
          <View style={styles.reasonList}>
            <Text style={[styles.reasonHeading, layout.isMobile && styles.reasonHeadingMobile]}>Why it fits</Text>
            {structured.keyFacts.slice(0, 3).map((fact) => (
              <View key={fact.text} style={styles.reasonRow}>
                <Ionicons name="checkmark-circle" size={15} color={colors.success} accessibilityElementsHidden />
                <Text style={[styles.reasonText, layout.isMobile && styles.reasonTextMobile]}>{fact.text}</Text>
              </View>
            ))}
          </View>
        ) : null}
        {structured.importantDrawbacks?.[0] ? (
          <View style={styles.cautionRow}>
            <Ionicons name="alert-circle-outline" size={16} color={colors.warning} accessibilityElementsHidden />
            <Text style={[styles.cautionText, layout.isMobile && styles.cautionTextMobile]}><Text style={styles.cautionStrong}>Before you buy: </Text>{structured.importantDrawbacks[0]}</Text>
          </View>
        ) : null}
        <View style={styles.primaryCta}>
          <Text style={[styles.primaryCtaText, layout.isMobile && styles.primaryCtaTextMobile]}>View product</Text>
          <Ionicons name="arrow-forward" size={15} color={colors.white} accessibilityElementsHidden />
        </View>
      </Pressable>

      {refs.alternatives.length ? (
        <View style={styles.alternatives}>
          <Text style={[styles.alternativesTitle, layout.isMobile && styles.alternativesTitleMobile]}>Other options</Text>
          {refs.alternatives.map((alternative, index) => {
            const alternativeProduct = alternative.productId ? getProduct(alternative.productId) : undefined;
            const alternativeTitle = alternativeProduct ? displayTitle(alternativeProduct) : alternative.title || 'Alternative product';
            return (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`View alternative product: ${alternativeTitle}`}
                key={`${alternative.productId || alternative.title}-${index}`}
                style={styles.alternativeCard}
                onPress={() => alternative.productId && (onOpenProduct ? onOpenProduct(alternative.productId) : router.push(`/product/${alternative.productId}`))}
              >
                <View style={styles.alternativeThumb}>
                  {alternativeProduct ? <ProductVisual product={alternativeProduct} size={62} /> : <View style={styles.refPlaceholder} />}
                </View>
                <View style={styles.alternativeCopy}>
                  <Text style={[styles.alternativeRole, layout.isMobile && styles.alternativeRoleMobile]}>{alternative.badge || 'ALTERNATIVE'}</Text>
                  <Text style={[styles.alternativeTitle, layout.isMobile && styles.alternativeTitleMobile]} numberOfLines={layout.isMobile ? undefined : 2}>{alternativeTitle}</Text>
                  <Text style={[styles.alternativeMeta, layout.isMobile && styles.alternativeMetaMobile]} numberOfLines={layout.isMobile ? undefined : 1}>{alternative.price != null ? `$${alternative.price.toFixed(2)}` : alternativeProduct ? displayPrice(alternativeProduct) : 'Price unavailable'}{alternative.specLine ? `  ·  ${alternative.specLine}` : ''}</Text>
                </View>
                <Ionicons name="chevron-forward" size={17} color={colors.textSoft} accessibilityElementsHidden />
              </Pressable>
            );
          })}
        </View>
      ) : null}
    </View>
  );
}

function comparisonLabel(label: string) {
  const normalized = label.trim().toLowerCase();
  const labels: Record<string, string> = {
    video: 'Video',
    'listed video': 'Listed video',
    connectors: 'Connectors',
    connector: 'Connector',
    length: 'Length',
    price: 'Price',
    performance: 'Performance',
    compatibility: 'Compatibility',
    reviews: 'Review evidence',
    distance: 'Distance',
  };
  return labels[normalized] || humanizeText(label);
}

function runSuggestedAction(
  action: SuggestedPickiAction,
  onQuickAction: (action: 'cheaper' | 'compare' | 'why_this') => void,
  onSendMessage: (text: string) => void,
) {
  if (action.href) {
    router.push(action.href as never);
    return;
  }
  if (action.kind === 'quick' && action.action) {
    onQuickAction(action.action);
    return;
  }
  if (action.message?.trim()) {
    onSendMessage(action.message.trim());
  }
}

const styles = StyleSheet.create({
  wrap: { marginTop: 8, gap: 10 },
  decision: { alignSelf: 'flex-start', borderRadius: radius.round, backgroundColor: '#E8F5EE', paddingVertical: 5, paddingHorizontal: 10 },
  decisionText: { color: colors.success, fontSize: 13, fontWeight: '700' },
  decisionTextMobile: { fontSize: 12 },
  refs: { gap: 8 },
  refRow: { flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
  refThumb: { width: 76, height: 76, borderRadius: radius.sm, overflow: 'hidden', backgroundColor: colors.surfaceMuted },
  refPlaceholder: { flex: 1, backgroundColor: colors.surfaceMuted },
  refCopy: { flex: 1, minWidth: 0, gap: 2 },
  refEyebrow: { color: colors.brand, fontSize: 9, fontWeight: '900', letterSpacing: 0.8 },
  refEyebrowMobile: { fontSize: 8 },
  refTitle: { color: colors.textPrimary, fontSize: 15, fontWeight: '700', lineHeight: 19 },
  refTitleMobile: { fontSize: 13, lineHeight: 17 },
  refPrice: { color: colors.brand, fontSize: 15, fontWeight: '800' },
  refPriceMobile: { fontSize: 14 },
  refSpec: { color: colors.textSecondary, fontSize: 12, lineHeight: 16 },
  refSpecMobile: { fontSize: 11, lineHeight: 15 },
  recommendations: { gap: 12 },
  primaryCard: { borderRadius: 16, borderWidth: 1, borderColor: '#E7DED8', backgroundColor: '#FFFCFA', padding: 14, gap: 12 },
  primaryLabelRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  primaryBadge: { flexDirection: 'row', alignItems: 'center', gap: 5, borderRadius: radius.round, backgroundColor: colors.brandSoft, paddingVertical: 5, paddingHorizontal: 9 },
  primaryBadgeText: { color: colors.brandInk, fontSize: 9, fontWeight: '900', letterSpacing: 0.8 },
  primaryBadgeTextMobile: { fontSize: 8 },
  evidenceStatus: { flexShrink: 1, color: colors.textSoft, fontSize: 10, fontWeight: '700', textAlign: 'right' },
  evidenceStatusMobile: { fontSize: 9 },
  primaryMain: { flexDirection: 'row', alignItems: 'center', gap: 13 },
  primaryThumb: { width: 104, height: 104, flexShrink: 0, borderRadius: 12, overflow: 'hidden', backgroundColor: colors.surfaceMuted },
  primaryCopy: { flex: 1, minWidth: 0, gap: 3 },
  primaryBrand: { color: colors.textSoft, fontSize: 9, fontWeight: '900', letterSpacing: 0.9, textTransform: 'uppercase' },
  primaryBrandMobile: { fontSize: 8 },
  primaryTitle: { color: colors.textPrimary, fontSize: 17, lineHeight: 21, fontWeight: '900', letterSpacing: -0.25 },
  primaryTitleMobile: { fontSize: 15, lineHeight: 19 },
  primaryPrice: { marginTop: 2, color: colors.brand, fontSize: 17, fontWeight: '900' },
  primaryPriceMobile: { fontSize: 15 },
  primarySpec: { color: colors.textSecondary, fontSize: 12, lineHeight: 17 },
  primarySpecMobile: { fontSize: 11, lineHeight: 15 },
  reasonList: { gap: 7, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: '#EEE8E3', paddingTop: 11 },
  reasonHeading: { color: colors.textPrimary, fontSize: 11, fontWeight: '900' },
  reasonHeadingMobile: { fontSize: 10 },
  reasonRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 7 },
  reasonText: { flex: 1, color: colors.textSecondary, fontSize: 12, lineHeight: 17 },
  reasonTextMobile: { fontSize: 11, lineHeight: 15 },
  cautionRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 7, borderRadius: 10, backgroundColor: colors.warningSoft, padding: 9 },
  cautionText: { flex: 1, color: '#7E4A27', fontSize: 11, lineHeight: 16 },
  cautionTextMobile: { fontSize: 10, lineHeight: 14 },
  cautionStrong: { fontWeight: '900' },
  primaryCta: { minHeight: 38, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderRadius: 11, backgroundColor: colors.brand },
  primaryCtaText: { color: colors.white, fontSize: 12, fontWeight: '900' },
  primaryCtaTextMobile: { fontSize: 11 },
  alternatives: { gap: 7 },
  alternativesTitle: { color: colors.textSoft, fontSize: 10, fontWeight: '900', letterSpacing: 0.7, textTransform: 'uppercase' },
  alternativesTitleMobile: { fontSize: 9 },
  alternativeCard: { minHeight: 78, flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: 13, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.white, padding: 8 },
  alternativeThumb: { width: 62, height: 62, flexShrink: 0, borderRadius: 9, overflow: 'hidden', backgroundColor: colors.surfaceMuted },
  alternativeCopy: { flex: 1, minWidth: 0, gap: 2 },
  alternativeRole: { color: colors.textSoft, fontSize: 8, fontWeight: '900', letterSpacing: 0.7 },
  alternativeRoleMobile: { fontSize: 7 },
  alternativeTitle: { color: colors.textPrimary, fontSize: 13, lineHeight: 17, fontWeight: '800' },
  alternativeTitleMobile: { fontSize: 12, lineHeight: 16 },
  alternativeMeta: { color: colors.textSecondary, fontSize: 11, lineHeight: 15 },
  alternativeMetaMobile: { fontSize: 10, lineHeight: 14 },
  compare: { gap: 10 },
  compareCards: { gap: 10, paddingRight: 2 },
  compareCardsDesktop: { width: '100%', flexDirection: 'row' },
  compareCardsMobile: { width: '100%', flexDirection: 'column', paddingRight: 0 },
  compareCardsMobilePair: { flexDirection: 'row', gap: 8 },
  compareCard: { width: 270, gap: 9, borderWidth: 1, borderColor: colors.border, borderRadius: 14, backgroundColor: colors.white, padding: 12 },
  compareCardDesktop: { flex: 1, width: 'auto' },
  compareCardMobile: { width: '100%' },
  compareCardMobilePair: { flex: 1, width: 'auto', minWidth: 0, padding: 9, gap: 7 },
  matchBadge: { alignSelf: 'flex-start', color: colors.success, fontSize: 11, fontWeight: '800' },
  matchBadgeMuted: { alignSelf: 'flex-start', color: colors.textSoft, fontSize: 11, fontWeight: '700' },
  matchBadgeMobile: { fontSize: 10 },
  compareThumb: { width: '100%', height: 96, borderRadius: radius.sm, overflow: 'hidden', backgroundColor: colors.surfaceMuted, marginBottom: 7, alignItems: 'center', justifyContent: 'center' },
  compareThumbMobilePair: { height: 76 },
  compareTitle: { minHeight: 40, color: colors.textPrimary, fontSize: 15, lineHeight: 20, fontWeight: '800' },
  compareTitleMobile: { fontSize: 13, lineHeight: 18 },
  comparePrice: { marginTop: 5, color: colors.brand, fontSize: 17, fontWeight: '900' },
  comparePriceMobile: { fontSize: 15 },
  cardFacts: { gap: 7, paddingTop: 9, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  cardFact: { gap: 2 },
  cardFactLabel: { color: colors.textSoft, fontSize: 11, fontWeight: '700' },
  cardFactLabelMobile: { fontSize: 10 },
  cardFactValue: { color: colors.textPrimary, fontSize: 13, lineHeight: 18 },
  cardFactValueMobile: { fontSize: 12, lineHeight: 16 },
  cardButtons: { marginTop: 'auto', gap: 7 },
  saveButton: { minHeight: 36, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, borderRadius: 9, backgroundColor: colors.brand },
  saveButtonSaved: { backgroundColor: '#EEF8F2', borderWidth: 1, borderColor: '#BFE1CC' },
  saveButtonText: { flexShrink: 1, color: colors.white, fontSize: 12, fontWeight: '800', textAlign: 'center' },
  saveButtonTextSaved: { color: colors.success },
  openButton: { minHeight: 34, alignItems: 'center', justifyContent: 'center', borderRadius: 9, borderWidth: 1, borderColor: colors.border },
  openButtonText: { color: colors.textPrimary, fontSize: 12, fontWeight: '700' },
  buttonTextMobile: { fontSize: 11 },
  detailBlock: { gap: 4 },
  detailToggle: { alignSelf: 'flex-start' },
  detailLabel: { color: colors.brand, fontSize: 13, fontWeight: '700' },
  detailLabelMobile: { fontSize: 12 },
  detailLines: { gap: 3, paddingLeft: 2 },
  detailLine: { color: colors.textSecondary, fontSize: 13, lineHeight: 18 },
  detailLineMobile: { fontSize: 12, lineHeight: 16 },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingTop: 2 },
  actionChip: {
    borderRadius: radius.round,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.white,
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  actionText: { color: colors.textPrimary, fontSize: 13, fontWeight: '700' },
  actionTextMobile: { fontSize: 12 },
});
