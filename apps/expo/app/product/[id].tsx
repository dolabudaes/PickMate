import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useRef, useState, type ComponentProps, type ReactNode } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { AppScreen } from '../../components/AppScreen';
import { ProductVisual } from '../../components/ProductVisual';
import { ResponsiveContainer } from '../../components/ResponsiveContainer';
import { useResponsiveLayout } from '../../components/responsive';
import { contentLineLimit, formatPrice, productTitle } from '../../lib/format';
import type { RelatedChat } from '../../lib/shoppingTurn';
import type { Product, Review } from '../../types';
import { usePickMate } from '../../store/PickMateStore';
import { conversationDisplayTitle } from '../../lib/demo';
import { colors, radius, shadow, spacing } from '../../theme';

type DetailRow = {
  key: string;
  value: string;
};
type IconName = ComponentProps<typeof Ionicons>['name'];

export default function ProductDetailScreen() {
  const params = useLocalSearchParams();
  const { getProduct, ensureProduct, loadingProducts } = usePickMate();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const product = getProduct(id);
  const requestedId = useRef<string | null>(null);
  useEffect(() => {
    if (!id || product?.reviews.length) return;
    if (requestedId.current === id) return;
    requestedId.current = id;
    void ensureProduct(id);
  }, [ensureProduct, id, product]);
  if (!product) {
    return (
      <AppScreen padded={false}>
        <View style={styles.missing}>
          <Text style={styles.topTitle}>{loadingProducts ? 'Loading product…' : 'Product not found'}</Text>
          {!loadingProducts ? <Pressable onPress={() => router.replace('/explore')} style={styles.askButton}><Text style={styles.askText}>Back to Explore</Text></Pressable> : null}
        </View>
      </AppScreen>
    );
  }
  return <ProductDetailContent product={product} />;
}

function ProductDetailContent({ product }: { product: Product }) {
  const insets = useSafeAreaInsets();
  const layout = useResponsiveLayout();
  const params = useLocalSearchParams();
  const fromChat = Array.isArray(params.from) ? params.from[0] : params.from;
  const { track, openProductInPicki, addToCart, cart } = usePickMate();
  const [askingPicki, setAskingPicki] = useState(false);
  const source = product.sourceFields;
  const inCart = cart.some((item) => item.productId === product.id);

  const features = useMemo(() => source?.features?.filter(Boolean) ?? [], [source]);
  const descriptions = useMemo(() => {
    const fromSource = source?.description?.filter(Boolean) ?? [];
    return fromSource.length ? fromSource : product.description ? [product.description] : [];
  }, [product.description, source]);
  const detailRows = useMemo(() => detailsFor(product).slice(0, 24), [product]);
  const reviews = useMemo(() => product.reviews.slice(0, 8), [product.reviews]);

  useEffect(() => {
    track('product_viewed', product.id);
  }, [product.id]);

  async function askPicki() {
    if (askingPicki) return;
    setAskingPicki(true);
    try {
      const request = openProductInPicki(product.id);
      router.push('/');
      await request;
    } catch (requestError) {
      Alert.alert('Picki is unavailable', requestError instanceof Error ? requestError.message : 'Please try again.');
    } finally {
      setAskingPicki(false);
    }
  }

  return (
    <AppScreen padded={false}>
      <ScrollView contentContainerStyle={[styles.content, { paddingBottom: layout.isDesktop ? 56 : 96 + insets.bottom }]}>
        <ResponsiveContainer>
          <View style={styles.topBar}>
            <Pressable onPress={() => router.back()} style={styles.iconButton}><Ionicons name="chevron-back" size={19} color={colors.textPrimary} /></Pressable>
            <Text style={styles.topTitle}>Product details</Text>
            <View style={styles.iconButton} />
          </View>

          <View style={[styles.hero, layout.isDesktop && styles.heroDesktop]}>
            <View style={[styles.gallery, layout.isDesktop && styles.galleryDesktop, shadow]}>
              <ProductVisual product={product} />
            </View>

            <View style={[styles.summary, layout.isDesktop && styles.summaryDesktop]}>
              <Text style={styles.sourceLabel}>{source?.brand || product.brand || ''}</Text>
              <Text style={[styles.title, layout.isDesktop && styles.titleDesktop]}>{productTitle(product)}</Text>
              <Text style={[styles.price, layout.isDesktop && styles.priceDesktop]}>{priceText(product)}</Text>
              <Text style={styles.priceNote}>Catalog reference price</Text>

              <View style={styles.buyRow}>
                <Pressable onPress={() => inCart ? router.push('/saved') : addToCart(product.id, { conversationId: fromChat || null, sourceType: fromChat ? 'chat' : 'product' })} style={styles.askButton}>
                  <Ionicons name={inCart ? 'checkmark-circle-outline' : 'bag-add-outline'} size={16} color={colors.white} />
                  <Text style={styles.askText}>{inCart ? 'View My Picks' : 'Save to My Picks'}</Text>
                </Pressable>
                <Pressable disabled={askingPicki} onPress={() => { void askPicki(); }} style={styles.secondaryButtonWide}>
                  <Ionicons name="sparkles-outline" size={16} color={colors.textPrimary} />
                  <Text style={styles.secondaryButtonText}>Ask Picki</Text>
                </Pressable>
              </View>
              <DiscussedThreads productId={product.id} />

              <View style={styles.metaGrid}>
                <MetaItem icon="folder-outline" label="Category" value={source?.mainCategory || product.category || '—'} complete={layout.isMobile} />
                <MetaItem icon="business-outline" label="Store" value={source?.store || product.sellerType || '—'} complete={layout.isMobile} />
                <MetaItem icon="star-outline" label="Rating" value={ratingText(product)} complete={layout.isMobile} />
                <MetaItem icon="chatbubbles-outline" label="Reviews" value={reviewCountText(source?.ratingNumber || product.reviewCount)} complete={layout.isMobile} />
              </View>

            </View>
          </View>

          <View style={[styles.sections, layout.isDesktop && styles.sectionsDesktop]}>
            <Section title="Product highlights" icon="list-outline" columns={layout.isDesktop}>
              {features.length ? (
                <View style={styles.bulletList}>
                  {features.slice(0, 12).map((item, index) => <Bullet key={`${index}-${item}`} text={item} />)}
                </View>
              ) : <EmptyLine text="No verified product highlights are available." />}
            </Section>

            <Section title="Product description" icon="document-text-outline" columns={layout.isDesktop}>
              {descriptions.length ? descriptions.slice(0, 5).map((item, index) => <Text key={`${index}-${item}`} style={styles.paragraph}>{item}</Text>) : <EmptyLine text="No product description is available." />}
            </Section>

            <Section title="Specifications" icon="grid-outline" columns={layout.isDesktop} wide={layout.isDesktop}>
              {detailRows.length ? (
                <View style={styles.detailsGrid}>
                  {detailRows.map((row) => (
                    <View key={row.key} style={styles.detailItem}>
                      <Text style={styles.detailKey}>{row.key}</Text>
                      <Text style={styles.detailValue}>{row.value}</Text>
                    </View>
                  ))}
                </View>
              ) : <EmptyLine text="No verified specifications are available." />}
            </Section>

            <Section title="Review evidence" icon="chatbox-ellipses-outline" columns={layout.isDesktop} wide={layout.isDesktop}>
              {reviews.length ? (
                <View style={styles.reviewList}>
                  {reviews.map((review) => <ReviewCard key={review.id} review={review} />)}
                </View>
              ) : <EmptyLine text="No verified review content is available, so Picki will not infer reliability from it." />}
            </Section>
          </View>
        </ResponsiveContainer>
      </ScrollView>

    </AppScreen>
  );
}

function Section({ title, icon, children, columns = false, wide = false }: { title: string; icon: IconName; children: ReactNode; columns?: boolean; wide?: boolean }) {
  return (
    <View style={[styles.section, columns && styles.sectionDesktop, wide && styles.sectionWide, shadow]}>
      <View style={styles.sectionHead}>
        <Ionicons name={icon} size={18} color={colors.brand} />
        <Text style={styles.sectionTitle}>{title}</Text>
      </View>
      {children}
    </View>
  );
}

function MetaItem({ icon, label, value, complete = false }: { icon: IconName; label: string; value: string; complete?: boolean }) {
  return (
    <View style={styles.metaItem}>
      <Ionicons name={icon} size={15} color={colors.textSoft} />
      <View style={styles.metaTextWrap}>
        <Text style={styles.metaLabel}>{label}</Text>
        <Text style={styles.metaValue} numberOfLines={contentLineLimit(complete, 2)}>{value}</Text>
      </View>
    </View>
  );
}

function Bullet({ text }: { text: string }) {
  return (
    <View style={styles.bulletRow}>
      <View style={styles.bulletDot} />
      <Text style={styles.bulletText}>{text}</Text>
    </View>
  );
}

function EmptyLine({ text }: { text: string }) {
  return <Text style={styles.emptyText}>{text}</Text>;
}

function ReviewCard({ review }: { review: Review }) {
  return (
    <View style={styles.reviewCard}>
      <View style={styles.reviewHead}>
        <Text style={styles.reviewRating}>{review.rating ? `${review.rating} stars` : 'Not rated'}</Text>
        <Text style={styles.reviewMeta}>{[review.verifiedPurchase ? 'Verified purchase' : '', reviewDate(review.createdAt)].filter(Boolean).join(' · ')}</Text>
      </View>
      <Text style={styles.reviewContent}>{review.content}</Text>
      {review.helpfulCount ? <Text style={styles.helpful}>{review.helpfulCount} found this helpful</Text> : null}
    </View>
  );
}

function priceText(product: Product) {
  if (product.sourceFields && product.sourceFields.price == null) return 'Price unavailable';
  return formatPrice(product);
}

function ratingText(product: Product) {
  const rating = product.sourceFields?.averageRating ?? product.rating;
  if (!rating) return '—';
  return `${rating.toFixed(1)} / 5`;
}

function reviewCountText(count: number) {
  if (!count) return '—';
  if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
  if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
  return `${count}`;
}

function reviewDate(value: string) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toISOString().slice(0, 10);
}

function detailsFor(product: Product): DetailRow[] {
  const source = product.sourceFields;
  const rows: DetailRow[] = [];
  if (source?.details) {
    for (const [key, value] of Object.entries(source.details)) {
      if (value == null || value === '') continue;
      rows.push({ key, value: Array.isArray(value) ? value.join(', ') : String(value) });
    }
  }
  if (!rows.length && product.attributes) {
    const attrs = product.attributes;
    if (attrs.batteryHours) rows.push({ key: 'Battery life', value: `${attrs.batteryHours} hours` });
    if (attrs.waterResistance) rows.push({ key: 'Water resistance', value: attrs.waterResistance });
    if (attrs.supportedCodecs?.length) rows.push({ key: 'Audio codecs', value: attrs.supportedCodecs.join(', ') });
  }
  return rows;
}

function DiscussedThreads({ productId }: { productId: string }) {
  const { relatedChats, selectConversation } = usePickMate();
  const [rows, setRows] = useState<RelatedChat[]>([]);
  useEffect(() => {
    let cancelled = false;
    void relatedChats(productId).then((items) => {
      if (!cancelled) setRows(items.slice(0, 3));
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [productId]);
  if (!rows.length) return null;
  return (
    <View style={styles.threads}>
      <Text style={styles.threadLabel}>Related Picki conversation</Text>
      {rows.map((item) => (
        <Pressable key={item.id} onPress={() => { void selectConversation(item.id); router.push('/'); }} style={styles.threadRow}>
          <Text style={styles.threadTitle} numberOfLines={1}>{conversationDisplayTitle(item)}</Text>
          <Ionicons name="arrow-forward-outline" size={15} color={colors.textSecondary} />
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingTop: spacing.md,
  },
  missing: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.md,
    padding: spacing.xl,
  },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  iconButton: {
    width: 38,
    height: 38,
    borderRadius: radius.round,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconButtonActive: {
    backgroundColor: colors.brand,
  },
  topTitle: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: '900',
  },
  hero: {
    marginTop: spacing.lg,
    gap: spacing.lg,
  },
  heroDesktop: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  gallery: {
    width: '100%',
    aspectRatio: 1,
    maxWidth: 560,
    minHeight: 280,
    borderRadius: radius.xl,
    backgroundColor: colors.surface,
    overflow: 'hidden',
  },
  galleryDesktop: {
    flex: 1,
    maxWidth: 520,
    minHeight: 420,
  },
  summary: {
    gap: spacing.md,
  },
  summaryDesktop: {
    flex: 1,
    minWidth: 0,
  },
  pickiPanel: {
    width: 300,
    borderRadius: radius.lg,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: '#FFD8C5',
    padding: spacing.lg,
  },
  pickiHead: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
  },
  pickiTitle: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: '900',
  },
  pickiText: {
    marginTop: 10,
    color: colors.textSecondary,
    fontSize: 13,
    lineHeight: 19,
  },
  pickiRisk: {
    marginTop: 10,
    borderRadius: radius.sm,
    backgroundColor: colors.warningSoft,
    color: colors.warning,
    padding: 9,
    fontSize: 12,
    lineHeight: 17,
  },
  panelAction: {
    marginTop: 14,
    alignItems: 'center',
    borderRadius: radius.sm,
    backgroundColor: colors.brand,
    paddingVertical: 11,
  },
  panelActionText: {
    color: colors.white,
    fontSize: 12,
    fontWeight: '900',
  },
  panelSecondary: {
    marginTop: 7,
    alignItems: 'center',
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: 10,
  },
  panelSecondaryText: {
    color: colors.textPrimary,
    fontSize: 12,
    fontWeight: '800',
  },
  sourceLabel: {
    color: colors.textSoft,
    fontSize: 12,
    fontWeight: '800',
  },
  title: {
    color: colors.textPrimary,
    fontSize: 24,
    fontWeight: '900',
    lineHeight: 30,
  },
  titleDesktop: {
    fontSize: 30,
    lineHeight: 36,
  },
  price: {
    color: colors.brand,
    fontSize: 26,
    fontWeight: '900',
  },
  priceDesktop: {
    fontSize: 30,
  },
  metaGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  askButton: {
    minHeight: 46,
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    borderRadius: 10,
    backgroundColor: colors.brand,
    paddingHorizontal: spacing.lg,
  },
  askText: {
    color: colors.white,
    fontWeight: '800',
    fontSize: 13,
  },
  askDisabled: { opacity: 0.45 },
  priceNote: { color: colors.textSoft, fontSize: 11, marginTop: -4 },
  buyRow: { marginTop: 18, gap: 10 },
  threads: { marginTop: 18, paddingTop: 16, borderTopWidth: 1, borderTopColor: colors.border, gap: 12 },
  threadLabel: { color: colors.textSecondary, fontSize: 12 },
  threadRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  threadTitle: { flex: 1, color: colors.textPrimary, fontSize: 13, fontWeight: '500' },
  secondaryButton: { minHeight: 44, flexGrow: 1, minWidth: 150, borderRadius: 11, borderWidth: 1, borderColor: '#E7E5E2', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 12, backgroundColor: colors.white },
  secondaryButtonWide: { width: '100%', minHeight: 44, borderRadius: 11, borderWidth: 1, borderColor: '#E7E5E2', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: colors.white },
  secondaryButtonText: { color: colors.textPrimary, fontSize: 13, fontWeight: '800' },
  metaItem: {
    width: '47%',
    flexDirection: 'row',
    gap: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceWarm,
    padding: spacing.sm,
  },
  metaTextWrap: {
    flex: 1,
    minWidth: 0,
  },
  metaLabel: {
    color: colors.textSoft,
    fontSize: 11,
    fontWeight: '800',
  },
  metaValue: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: '800',
  },
  sections: {
    gap: spacing.lg,
    marginTop: spacing.xl,
  },
  sectionsDesktop: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  section: {
    borderRadius: radius.lg,
    backgroundColor: colors.surface,
    padding: spacing.lg,
  },
  sectionDesktop: {
    width: '48%',
  },
  sectionWide: {
    width: '100%',
  },
  sectionHead: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  sectionTitle: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: '900',
  },
  bulletList: {
    gap: spacing.sm,
  },
  bulletRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  bulletDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.brand,
    marginTop: 7,
  },
  bulletText: {
    flex: 1,
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 21,
  },
  paragraph: {
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 22,
    marginBottom: spacing.sm,
  },
  detailsGrid: {
    gap: spacing.sm,
  },
  detailItem: {
    flexDirection: 'row',
    gap: spacing.md,
    paddingVertical: 6,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  detailKey: {
    width: 108,
    flexShrink: 0,
    color: colors.textSoft,
    fontSize: 13,
    fontWeight: '800',
  },
  detailValue: {
    flex: 1,
    color: colors.textPrimary,
    fontSize: 13,
    lineHeight: 20,
  },
  reviewList: {
    gap: spacing.md,
  },
  reviewCard: {
    borderRadius: radius.md,
    backgroundColor: colors.surfaceWarm,
    padding: spacing.md,
  },
  reviewHead: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  reviewRating: {
    color: colors.textPrimary,
    fontWeight: '900',
  },
  reviewMeta: {
    color: colors.textSoft,
    fontSize: 12,
  },
  reviewContent: {
    marginTop: spacing.sm,
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 21,
  },
  helpful: {
    marginTop: spacing.sm,
    color: colors.textSoft,
    fontSize: 12,
  },
  emptyText: {
    color: colors.textSoft,
    fontSize: 13,
  },
  mobileBar: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: 'row',
    gap: 8,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    backgroundColor: colors.surface,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  mobilePrimary: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    borderRadius: radius.lg,
    backgroundColor: colors.brand,
    paddingVertical: 14,
  },
  mobilePrimaryText: {
    color: colors.white,
    fontWeight: '900',
    fontSize: 15,
  },
  mobileSecondary: {
    minWidth: 104,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.brand,
    paddingVertical: 14,
  },
  mobileSecondaryText: {
    color: colors.brand,
    fontWeight: '900',
    fontSize: 13,
  },
});
