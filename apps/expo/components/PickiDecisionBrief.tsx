import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { displayPrice, displayTitle } from '../lib/format';
import type { StructuredPickiResponse } from '../lib/shoppingTurn';
import type { Product } from '../types';
import { colors, radius } from '../theme';
import { ProductVisual } from './ProductVisual';
import { useResponsiveLayout } from './responsive';

export function PickiDecisionBrief({
  structured,
  getProduct,
  onSendMessage,
}: {
  structured: StructuredPickiResponse;
  getProduct: (id: string) => Product | undefined;
  onSendMessage: (text: string) => void;
}) {
  const layout = useResponsiveLayout();
  const brief = structured.decisionBrief;
  const [openEvidence, setOpenEvidence] = useState(false);
  if (!brief) return null;
  const refs = (structured.productRefs || []).slice(0, 2);
  const comparison = structured.comparisonData;

  return (
    <View style={styles.wrap}>
      {refs.length ? (
        <View style={styles.cards}>
          {refs.map((ref) => {
            const product = ref.productId ? getProduct(ref.productId) : undefined;
            const chosen = ref.productId && ref.productId === brief.winnerProductId;
            return (
              <Pressable
                key={`${ref.productId}-${ref.role}`}
                style={[styles.card, chosen && styles.cardOn]}
                onPress={() => ref.productId && router.push(`/product/${ref.productId}`)}
              >
                <View style={styles.thumb}>{product ? <ProductVisual product={product} size={52} /> : null}</View>
                <Text style={[styles.cardTitle, layout.isMobile && styles.cardTitleMobile]} numberOfLines={2}>{ref.title || (product ? displayTitle(product) : 'Product')}</Text>
                {ref.specLine ? <Text style={[styles.cardSpec, layout.isMobile && styles.cardSpecMobile]} numberOfLines={1}>{ref.specLine}</Text> : null}
                <Text style={[styles.cardPrice, layout.isMobile && styles.cardPriceMobile]}>{ref.price != null ? `$${ref.price.toFixed(2)}` : product ? displayPrice(product) : 'Price unavailable'}</Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}

      {brief.angles?.length ? (
        <View style={styles.angles}>
          {brief.angles.slice(0, 3).map((angle) => (
            <View key={angle.id || angle.title} style={styles.angle}>
              <Text style={[styles.angleTitle, layout.isMobile && styles.angleTitleMobile]}>{angle.title}</Text>
              <Text style={[styles.angleBody, layout.isMobile && styles.angleBodyMobile]}>{angle.body}</Text>
            </View>
          ))}
        </View>
      ) : null}

      {brief.gap ? <Text style={[styles.gap, layout.isMobile && styles.bodyMobile]}>{brief.gap}</Text> : null}
      {brief.changeCondition ? (
        <Text style={[styles.change, layout.isMobile && styles.bodyMobile]}>{brief.changeCondition}</Text>
      ) : null}

      {brief.switches?.length ? (
        <View style={styles.switchBlock}>
          <Text style={[styles.switchLabel, layout.isMobile && styles.switchLabelMobile]}>What could change this choice?</Text>
          <View style={styles.switchRow}>
            {brief.switches.map((item) => (
              <Pressable key={item.id} onPress={() => onSendMessage(item.message)} style={styles.switchChip}>
                <Text style={[styles.switchText, layout.isMobile && styles.switchTextMobile]}>{item.label}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      ) : null}

      {(brief.evidence?.length || comparison?.rows?.length || brief.review?.quotes?.length) ? (
        <View>
          <Pressable onPress={() => setOpenEvidence((value) => !value)}>
            <Text style={[styles.toggle, layout.isMobile && styles.toggleMobile]}>{openEvidence ? 'Hide evidence' : 'View evidence'}</Text>
          </Pressable>
          {openEvidence ? (
            <View style={styles.evidence}>
              {comparison?.rows?.map((row) => (
                <Text key={row.label} style={[styles.evidenceLine, layout.isMobile && styles.evidenceLineMobile]}>{row.label}: {row.values.join(' · ')}</Text>
              ))}
              {(brief.review?.quotes || []).map((quote, index) => (
                <Text key={`${quote.productId}-${index}`} style={[styles.quote, layout.isMobile && styles.evidenceLineMobile]}>“{quote.snippet}”</Text>
              ))}
              {(brief.evidence || []).filter((item) => item.availability === 'verified').slice(0, 4).map((item, index) => (
                <Text key={`${item.productId}-${index}`} style={[styles.evidenceLine, layout.isMobile && styles.evidenceLineMobile]}>{item.claim}</Text>
              ))}
            </View>
          ) : null}
        </View>
      ) : null}

      {structured.suggestedActions?.length ? (
        <View style={styles.actions}>
          {structured.suggestedActions.slice(0, 3).map((action) => (
            <Pressable
              key={action.id}
              onPress={() => {
                if (action.href) {
                  router.push(action.href as never);
                  return;
                }
                if (action.message) onSendMessage(action.message);
              }}
              style={styles.action}
            >
              <Text style={[styles.actionText, layout.isMobile && styles.actionTextMobile]}>{action.label}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: 10, gap: 10 },
  cards: { flexDirection: 'row', gap: 10 },
  card: { flex: 1, minWidth: 0, gap: 4 },
  cardOn: { opacity: 1 },
  thumb: { width: 52, height: 52, borderRadius: 8, overflow: 'hidden', backgroundColor: colors.surfaceMuted },
  cardTitle: { color: colors.textPrimary, fontSize: 13, fontWeight: '700', lineHeight: 17 },
  cardTitleMobile: { fontSize: 12, lineHeight: 16 },
  cardSpec: { color: colors.textSecondary, fontSize: 12 },
  cardSpecMobile: { fontSize: 11 },
  cardPrice: { color: colors.brand, fontSize: 14, fontWeight: '800' },
  cardPriceMobile: { fontSize: 13 },
  angles: { gap: 8 },
  angle: { gap: 2 },
  angleTitle: { color: colors.textSoft, fontSize: 11, fontWeight: '700', letterSpacing: 0.3 },
  angleTitleMobile: { fontSize: 10 },
  angleBody: { color: colors.textPrimary, fontSize: 13, lineHeight: 18 },
  angleBodyMobile: { fontSize: 12, lineHeight: 16 },
  gap: { color: colors.textSecondary, fontSize: 13, lineHeight: 18 },
  change: { color: colors.textPrimary, fontSize: 13, lineHeight: 18 },
  bodyMobile: { fontSize: 12, lineHeight: 16 },
  switchBlock: { gap: 6, paddingTop: 2 },
  switchLabel: { color: colors.textSoft, fontSize: 12, fontWeight: '700' },
  switchLabelMobile: { fontSize: 11 },
  switchRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  switchChip: { borderRadius: radius.round, borderWidth: 1, borderColor: colors.border, paddingVertical: 7, paddingHorizontal: 11, backgroundColor: colors.white },
  switchText: { color: colors.textPrimary, fontSize: 12, fontWeight: '700' },
  switchTextMobile: { fontSize: 11 },
  toggle: { color: colors.brand, fontSize: 13, fontWeight: '700' },
  toggleMobile: { fontSize: 12 },
  evidence: { gap: 4, paddingTop: 4 },
  evidenceLine: { color: colors.textSecondary, fontSize: 12, lineHeight: 17 },
  quote: { color: colors.textSecondary, fontSize: 12, lineHeight: 17, fontStyle: 'italic' },
  evidenceLineMobile: { fontSize: 11, lineHeight: 15 },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingTop: 2 },
  action: { borderRadius: radius.round, backgroundColor: colors.brandSoft, paddingVertical: 8, paddingHorizontal: 12 },
  actionText: { color: colors.brandInk, fontSize: 13, fontWeight: '700' },
  actionTextMobile: { fontSize: 12 },
});
