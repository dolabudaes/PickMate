import { Ionicons } from '@expo/vector-icons';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { contentLineLimit, displayPrice, displayTitle } from '../lib/format';
import type { Product } from '../types';
import { colors, radius, shadow, spacing } from '../theme';
import { ProductVisual } from './ProductVisual';
import { useResponsiveLayout } from './responsive';

export function ProductCard({
  product,
  onOpen,
  onCompare,
  onAdd,
  onAskPicki,
  inCart = false,
  compared = false,
}: {
  product: Product;
  onOpen: () => void;
  onCompare?: () => void;
  onAdd?: () => void;
  onAskPicki?: () => void;
  inCart?: boolean;
  compared?: boolean;
}) {
  const layout = useResponsiveLayout();
  return (
    <Pressable
      onPress={onOpen}
      style={({ hovered, pressed }) => StyleSheet.flatten([
        styles.card,
        layout.isDesktop && styles.cardDesktop,
        layout.isDesktop && shadow,
        Platform.OS === 'web' && layout.isDesktop && hovered && styles.cardHover,
        pressed && styles.cardPressed,
      ])}
    >
      <View style={StyleSheet.flatten([styles.visual, layout.isMobile && styles.visualMobile, layout.isDesktop && styles.visualDesktop])}>
        <ProductVisual product={product} />
        {onCompare ? (
          <Pressable accessibilityRole="button" accessibilityLabel={compared ? 'Remove from comparison' : 'Add to comparison'} onPress={(event) => { event.stopPropagation(); onCompare(); }} style={StyleSheet.flatten([styles.save, compared && styles.saveActive])}>
            <Ionicons name={compared ? 'git-compare' : 'git-compare-outline'} size={16} color={compared ? colors.white : colors.textPrimary} />
          </Pressable>
        ) : null}
        {onAdd ? (
          <Pressable accessibilityRole="button" accessibilityLabel={inCart ? 'View My Picks' : 'Save to My Picks'} onPress={(event) => { event.stopPropagation(); onAdd(); }} style={styles.add}>
            <Ionicons name={inCart ? 'checkmark' : 'add'} size={18} color={inCart ? colors.success : colors.textPrimary} />
          </Pressable>
        ) : null}
      </View>
      <View style={StyleSheet.flatten([styles.body, layout.isMobile && styles.bodyMobile, layout.isDesktop && styles.bodyDesktop])}>
        <Text style={[styles.brand, layout.isMobile && styles.brandMobile]} numberOfLines={contentLineLimit(layout.isMobile, 1)}>{product.brand}{product.category ? ` / ${product.category}` : ''}</Text>
        <Text style={StyleSheet.flatten([styles.title, layout.isMobile && styles.titleMobile, layout.isDesktop && styles.titleDesktop])} numberOfLines={contentLineLimit(layout.isMobile, 2)}>{displayTitle(product)}</Text>
        <View style={styles.priceRow}>
          <Text style={StyleSheet.flatten([styles.price, layout.isDesktop && styles.priceDesktop])} numberOfLines={1}>{displayPrice(product)}</Text>
          {product.rating ? <Text style={styles.rating}>★ {product.rating.toFixed(1)}</Text> : null}
        </View>
        {onAskPicki ? (
          <Pressable onPress={(event) => { event.stopPropagation(); onAskPicki(); }} style={styles.pickiButton}>
            <Ionicons name="sparkles" size={14} color={colors.brand} />
            <Text style={styles.pickiText}>Ask Picki</Text>
          </Pressable>
        ) : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    overflow: 'hidden',
    backgroundColor: colors.surface,
  },
  cardDesktop: {
    borderRadius: radius.lg,
  },
  cardHover: {
    transform: [{ translateY: -2 }],
    boxShadow: '0 8px 22px rgba(34,34,34,0.10)',
  },
  cardPressed: {
    opacity: 0.88,
    transform: [{ scale: 0.99 }],
  },
  visual: {
    width: '100%',
    aspectRatio: 1,
    borderRadius: 15,
    overflow: 'hidden',
    backgroundColor: colors.surfaceMuted,
  },
  visualMobile: {
    aspectRatio: 1.18,
    borderRadius: 12,
  },
  add: {
    position: 'absolute',
    right: 12,
    top: 12,
    width: 34,
    height: 34,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 17,
    backgroundColor: colors.white,
  },
  visualDesktop: {
    aspectRatio: 1.12,
  },
  save: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 30,
    height: 30,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.round,
    backgroundColor: 'rgba(255,255,255,0.88)',
  },
  saveActive: {
    backgroundColor: colors.brand,
  },
  body: {
    padding: 10,
  },
  bodyMobile: {
    paddingHorizontal: 7,
    paddingVertical: 7,
  },
  bodyDesktop: {
    padding: 12,
  },
  brand: {
    color: colors.textSoft,
    fontSize: 10,
    fontWeight: '800',
    textTransform: 'uppercase',
  },
  brandMobile: {
    fontSize: 9,
  },
  title: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: '900',
    lineHeight: 18,
  },
  titleMobile: {
    fontSize: 12,
    lineHeight: 16,
  },
  titleDesktop: {
    fontSize: 14,
    lineHeight: 19,
  },
  value: {
    marginTop: 5,
    color: colors.textSecondary,
    fontSize: 12,
  },
  priceRow: { marginTop: 6, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  price: {
    flexShrink: 1,
    color: colors.textPrimary,
    fontSize: 15,
    fontWeight: '600',
  },
  priceDesktop: {
    fontSize: 21,
  },
  rating: {
    marginTop: 2,
    color: colors.textSoft,
    fontSize: 11,
    fontWeight: '800',
  },
  ratingDesktop: {
    fontSize: 12,
  },
  feature: {
    marginTop: 5,
    color: colors.textSecondary,
    fontSize: 11,
  },
  actions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 6,
    marginTop: 10,
  },
  pickiButton: {
    flex: 1,
    minHeight: 32,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    borderRadius: radius.sm,
    backgroundColor: colors.brandSoft,
  },
  pickiText: {
    color: colors.brand,
    fontSize: 10,
    fontWeight: '800',
  },
  detailsButton: {
    minHeight: 32,
    justifyContent: 'center',
    paddingHorizontal: 8,
  },
  detailsText: {
    color: colors.textSecondary,
    fontSize: 10,
    fontWeight: '800',
  },
});
