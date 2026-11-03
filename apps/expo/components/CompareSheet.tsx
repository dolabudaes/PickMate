import { router } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { AccessibilityInfo, Animated, Easing, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { displayTitle } from '../lib/format';
import type { ComparisonExplanation, ComparisonRecord } from '../lib/shoppingTurn';
import type { Product } from '../types';
import { usePickMate } from '../store/PickMateStore';
import { colors, spacing } from '../theme';
import { ProductVisual } from './ProductVisual';
import { useResponsiveLayout } from './responsive';

export function CompareSheet() {
  const layout = useResponsiveLayout();
  const { activeComparison, closeComparison, getProduct, askAboutComparison, keepComparisonPick } = usePickMate();
  const explanation = useMemo(() => (activeComparison ? buildExplanation(activeComparison) : null), [activeComparison]);

  useEffect(() => {
    if (!activeComparison) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeComparison();
    };
    if (typeof window !== 'undefined') window.addEventListener('keydown', onKey);
    return () => {
      if (typeof window !== 'undefined') window.removeEventListener('keydown', onKey);
    };
  }, [activeComparison, closeComparison]);

  if (!activeComparison || !explanation) return null;

  const body = (
    <CompareBody
      record={activeComparison}
      explanation={explanation}
      isMobile={layout.isMobile}
      getProduct={getProduct}
      onClose={closeComparison}
      onAsk={() => { void askAboutComparison().then(() => router.push('/')); }}
      onKeep={() => { void keepComparisonPick(); }}
    />
  );

  if (layout.isDesktop) {
    return (
      <View style={styles.desktopHost} accessibilityViewIsModal>
        <Pressable style={styles.scrim} onPress={closeComparison} accessibilityLabel="Close comparison" />
        <View style={styles.sheetDesktop}>{body}</View>
      </View>
    );
  }

  return (
    <View style={styles.mobileHost} accessibilityViewIsModal>
      <Pressable style={styles.scrim} onPress={closeComparison} />
      <SafeAreaView style={styles.mobileSafe} edges={['bottom']}>
        <View style={styles.sheetMobile}>{body}</View>
      </SafeAreaView>
    </View>
  );
}

function CompareBody({
  record,
  explanation,
  isMobile,
  getProduct,
  onClose,
  onAsk,
  onKeep,
}: {
  record: ComparisonRecord;
  explanation: ComparisonExplanation;
  isMobile: boolean;
  getProduct: (id: string) => Product | undefined;
  onClose: () => void;
  onAsk: () => void;
  onKeep: () => void;
}) {
  const [reduceMotion, setReduceMotion] = useState(false);
  const panel = useRef(new Animated.Value(0)).current;
  const takeAnim = useRef(new Animated.Value(0)).current;
  const table = useRef(new Animated.Value(0)).current;
  const actions = useRef(new Animated.Value(0)).current;
  const take = explanation.verdict || record.verdict || explanation.summary || '';

  useEffect(() => {
    AccessibilityInfo.isReduceMotionEnabled().then(setReduceMotion).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (reduceMotion) {
      panel.setValue(1);
      takeAnim.setValue(1);
      table.setValue(1);
      actions.setValue(1);
      return;
    }
    panel.setValue(0);
    takeAnim.setValue(0);
    table.setValue(0);
    actions.setValue(0);
    Animated.timing(panel, { toValue: 1, duration: 200, easing: Easing.out(Easing.cubic), useNativeDriver: true }).start();
    const takeTimer = setTimeout(() => Animated.timing(takeAnim, { toValue: 1, duration: 220, useNativeDriver: true }).start(), 80);
    const a = setTimeout(() => Animated.timing(table, { toValue: 1, duration: 220, useNativeDriver: true }).start(), 220);
    const b = setTimeout(() => Animated.timing(actions, { toValue: 1, duration: 200, useNativeDriver: true }).start(), 380);
    return () => { clearTimeout(takeTimer); clearTimeout(a); clearTimeout(b); };
  }, [record.id, reduceMotion, panel, takeAnim, table, actions]);

  return (
    <Animated.View style={[styles.bodyWrap, { opacity: panel, transform: [{ scale: panel.interpolate({ inputRange: [0, 1], outputRange: [0.98, 1] }) }] }]}>
      <View style={styles.head}>
        <Text style={styles.kicker}>Picki's Take</Text>
        <Pressable onPress={onClose} accessibilityLabel="Close" style={styles.closeButton}>
          <Text style={styles.close}>Close</Text>
        </Pressable>
      </View>
      <ScrollView contentContainerStyle={[styles.scrollBody, isMobile && styles.scrollBodyMobile]} showsVerticalScrollIndicator={false}>
        {take ? (
          <Animated.View style={{ opacity: takeAnim, transform: [{ translateY: takeAnim.interpolate({ inputRange: [0, 1], outputRange: [6, 0] }) }] }}>
            <Text style={styles.take}>{take}</Text>
          </Animated.View>
        ) : null}

        <Animated.View style={{ opacity: table, transform: [{ translateY: table.interpolate({ inputRange: [0, 1], outputRange: [6, 0] }) }] }}>
          <View style={[styles.pair, isMobile && styles.pairMobile]}>
            {record.products.slice(0, 2).map((item) => {
              const product = getProduct(item.productId);
              const chosen = item.productId === explanation.winnerProductId;
              return (
                <Pressable key={item.productId} style={styles.pairItem} onPress={() => router.push(`/product/${item.productId}`)}>
                  <View style={styles.thumb}>{product ? <ProductVisual product={product} size={44} /> : null}</View>
                  <Text style={[styles.pairName, chosen && styles.pairNameOn]} numberOfLines={isMobile ? undefined : 2}>
                    {product ? displayTitle(product) : item.title}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          {explanation.diffs.slice(0, 4).map((row) => (
            <View key={row.label} style={styles.diffRow}>
              <Text style={styles.diffLabel}>{row.label}</Text>
              <View style={[styles.diffValues, isMobile && styles.diffValuesMobile]}>
                {row.values.slice(0, 2).map((value, index) => (
                  isMobile ? (
                    <View key={`${row.label}-${index}`} style={styles.diffValueMobileRow}>
                      <Text style={styles.diffProductName}>
                        {record.products[index]?.productId && getProduct(record.products[index].productId)
                          ? displayTitle(getProduct(record.products[index].productId)!)
                          : record.products[index]?.title || `Product ${index + 1}`}
                      </Text>
                      <Text style={styles.diffValueMobile}>{value || 'Not provided'}</Text>
                    </View>
                  ) : <Text key={`${row.label}-${index}`} style={styles.diffValue}>{value || 'Not provided'}</Text>
                ))}
              </View>
            </View>
          ))}
        </Animated.View>
      </ScrollView>
      <Animated.View style={[styles.foot, { opacity: actions }]} pointerEvents="auto">
        {explanation.winnerProductId ? (
          <Pressable onPress={onKeep} style={styles.keep}><Text style={styles.keepText}>Keep this pick</Text></Pressable>
        ) : null}
        <Pressable onPress={onAsk} style={styles.ghost}><Text style={styles.ghostText}>Ask Picki</Text></Pressable>
      </Animated.View>
    </Animated.View>
  );
}

function buildExplanation(record: ComparisonRecord): ComparisonExplanation {
  if (record.explanation?.verdict || record.explanation?.headline) {
    return {
      ...record.explanation,
      winnerProductId: record.explanation.winnerProductId ?? record.winnerProductId,
      verdict: record.explanation.verdict || record.verdict,
      reasons: [],
      preferenceNote: null,
    };
  }
  return {
    winnerProductId: record.winnerProductId,
    headline: "Picki's take",
    summary: '',
    verdict: record.verdict,
    reasons: [],
    diffs: [
      { label: 'Price', values: record.products.map((item) => (item.referencePrice != null ? `$${item.referencePrice.toFixed(2)}` : 'Not provided')) },
    ],
    preferenceNote: null,
    limitation: null,
  };
}

const styles = StyleSheet.create({
  desktopHost: { ...StyleSheet.absoluteFillObject, zIndex: 1900, justifyContent: 'center', padding: spacing.lg },
  mobileHost: { ...StyleSheet.absoluteFillObject, zIndex: 1900, justifyContent: 'flex-end' },
  scrim: { ...StyleSheet.absoluteFillObject, backgroundColor: colors.overlay },
  mobileSafe: { width: '100%' },
  sheetDesktop: {
    width: '100%',
    maxWidth: 640,
    maxHeight: '78%',
    alignSelf: 'center',
    borderRadius: 18,
    backgroundColor: colors.white,
    overflow: 'hidden',
    zIndex: 1,
  },
  sheetMobile: {
    width: '100%',
    maxHeight: '92%',
    borderTopLeftRadius: 18,
    borderTopRightRadius: 18,
    backgroundColor: colors.white,
    overflow: 'hidden',
  },
  bodyWrap: { flexShrink: 1, maxHeight: '100%' },
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 20, paddingTop: 16, paddingBottom: 4 },
  kicker: { color: colors.textPrimary, fontSize: 20, fontWeight: '800', letterSpacing: -0.3 },
  closeButton: { minWidth: 44, minHeight: 44, alignItems: 'flex-end', justifyContent: 'center' },
  close: { color: colors.textSecondary, fontSize: 14, fontWeight: '600' },
  scrollBody: { paddingHorizontal: 20, paddingBottom: 6 },
  scrollBodyMobile: { paddingHorizontal: 16, paddingBottom: 16 },
  take: { color: colors.textPrimary, fontSize: 16, fontWeight: '500', letterSpacing: -0.15, lineHeight: 23, marginBottom: 4 },
  pair: { flexDirection: 'row', gap: 14, marginTop: 14, marginBottom: 8 },
  pairMobile: { flexDirection: 'column', gap: 8 },
  pairItem: { flex: 1, flexDirection: 'row', gap: 8, alignItems: 'center' },
  thumb: { width: 44, height: 44, borderRadius: 8, overflow: 'hidden', backgroundColor: colors.surfaceMuted },
  pairName: { flex: 1, color: colors.textPrimary, fontSize: 13, fontWeight: '600', lineHeight: 17 },
  pairNameOn: { color: colors.brandInk },
  diffRow: { paddingVertical: 7, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  diffLabel: { color: colors.textSoft, fontSize: 12, fontWeight: '700', marginBottom: 3 },
  diffValues: { flexDirection: 'row', gap: 12 },
  diffValuesMobile: { flexDirection: 'column', gap: 6 },
  diffValue: { flex: 1, color: colors.textPrimary, fontSize: 14, lineHeight: 19 },
  diffValueMobileRow: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 },
  diffProductName: { flex: 1, color: colors.textSecondary, fontSize: 12, lineHeight: 17 },
  diffValueMobile: { maxWidth: '42%', color: colors.textPrimary, fontSize: 14, lineHeight: 19, fontWeight: '700', textAlign: 'right' },
  foot: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, paddingHorizontal: 20, paddingVertical: 12, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  keep: { minHeight: 44, borderRadius: 10, backgroundColor: colors.brand, paddingHorizontal: 14, justifyContent: 'center' },
  keepText: { color: colors.white, fontSize: 13, fontWeight: '700' },
  ghost: { minHeight: 44, borderRadius: 10, paddingHorizontal: 12, justifyContent: 'center' },
  ghostText: { color: colors.textPrimary, fontSize: 13, fontWeight: '700' },
});
