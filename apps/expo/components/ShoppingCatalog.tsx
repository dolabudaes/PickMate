import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { Product } from '../types';
import { usePickMate } from '../store/PickMateStore';
import { colors, radius, spacing } from '../theme';
import { ProductCard } from './ProductCard';
import { ResponsiveContainer } from './ResponsiveContainer';
import { useResponsiveLayout } from './responsive';

type SortMode = 'recommended' | 'rating' | 'reviews' | 'price_low' | 'price_high';

export function ShoppingCatalog({ compact = false }: { compact?: boolean }) {
  const layout = useResponsiveLayout();
  const insets = useSafeAreaInsets();
  const { products, catalogCount, catalogBrands, loadingProducts, error, reloadProducts, searchCatalog, addToCart, cart, openProductInPicki } = usePickMate();
  const [query, setQuery] = useState('');
  const [brand, setBrand] = useState('All');
  const [maxPrice, setMaxPrice] = useState<number | null>(null);
  const [sort, setSort] = useState<SortMode>(compact ? 'reviews' : 'recommended');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [pageItems, setPageItems] = useState<Product[]>(products);
  const [pageCount, setPageCount] = useState(products.length);
  const [searching, setSearching] = useState(false);
  const [offset, setOffset] = useState(0);

  const brands = useMemo(() => ['All', ...catalogBrands], [catalogBrands]);

  useEffect(() => {
    if (compact) {
      setPageItems(products.slice(0, layout.isDesktop ? 8 : 4));
      setPageCount(products.length);
      return;
    }
    let cancelled = false;
    setSearching(true);
    const timer = setTimeout(() => {
      void searchCatalog({ q: query, brand, maxPrice, sort, offset, limit: 24 }).then((page) => {
        if (cancelled) return;
        setPageItems(page.items);
        setPageCount(page.count);
        setSearching(false);
      }).catch(() => {
        if (!cancelled) setSearching(false);
      });
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [brand, compact, layout.isDesktop, maxPrice, offset, products, query, searchCatalog, sort]);

  const visible = compact ? products.slice(0, layout.isDesktop ? 8 : 4) : pageItems;

  const controls = (
    <FilterControls
      brands={brands}
      brand={brand}
      maxPrice={maxPrice}
      sort={sort}
      onBrand={(value) => { setBrand(value); setOffset(0); }}
      onMaxPrice={(value) => { setMaxPrice(value); setOffset(0); }}
      onSort={(value) => { setSort(value); setOffset(0); }}
      onReset={() => { setBrand('All'); setMaxPrice(null); setSort('recommended'); setOffset(0); }}
    />
  );

  return (
    <View style={styles.root}>
      <ResponsiveContainer>
        {compact ? null : (
          <>
            <View style={[styles.searchHeader, layout.isDesktop && styles.searchHeaderDesktop]}>
              <View style={styles.search}>
                <Ionicons name="search-outline" size={18} color={colors.textSecondary} />
                <TextInput
                  accessibilityLabel="Search products"
                  value={query}
                  onChangeText={(value) => { setQuery(value); setOffset(0); }}
                  placeholder="Search products, brands, or specifications"
                  placeholderTextColor={colors.textSoft}
                  style={styles.searchInput}
                />
                {query ? <Pressable onPress={() => setQuery('')}><Ionicons name="close-circle" size={18} color={colors.textSoft} /></Pressable> : null}
              </View>
              {!layout.isDesktop ? (
                <Pressable onPress={() => setFiltersOpen(true)} style={styles.filterButton}>
                  <Ionicons name="options-outline" size={18} color={colors.textPrimary} />
                </Pressable>
              ) : null}
            </View>

              {!layout.isDesktop ? (
                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  style={styles.mobileFiltersScroll}
                  contentContainerStyle={styles.mobileFilters}
                >
                  <QuickFilter label="All" active={brand === 'All' && maxPrice == null} onPress={() => { setBrand('All'); setMaxPrice(null); setOffset(0); }} />
                  <QuickFilter label="Top rated" active={sort === 'rating'} onPress={() => setSort('rating')} />
                  <QuickFilter label="Most reviewed" active={sort === 'reviews'} onPress={() => setSort('reviews')} />
                  <QuickFilter label="Lowest price" active={sort === 'price_low'} onPress={() => setSort('price_low')} />
                </ScrollView>
              ) : null}
          </>
        )}

        <View style={styles.resultHead}>
          <View>
            <Text style={styles.resultTitle}>{compact ? 'Explore audio and connection gear' : brand === 'All' ? 'All products' : brand}</Text>
            <Text style={styles.resultCount}>
              {catalogCount == null ? 'Catalog count unavailable' : `${catalogCount.toLocaleString()} products in the catalog`}
              {!compact ? ` · Showing ${visible.length}` : ''}
            </Text>
          </View>
          {compact ? <Pressable onPress={() => router.push('/explore')}><Text style={styles.viewAll}>View all</Text></Pressable> : null}
        </View>

        {loadingProducts || (!compact && searching) ? (
          <View style={styles.state}><ActivityIndicator color={colors.brand} /><Text style={styles.stateText}>Loading the catalog…</Text></View>
        ) : error && !products.length ? (
          <View style={styles.state}>
            <Ionicons name="cloud-offline-outline" size={28} color={colors.warning} />
            <Text style={styles.stateTitle}>The catalog is temporarily unavailable</Text>
            <Text style={styles.stateText}>{error}</Text>
            <Pressable onPress={reloadProducts} style={styles.retry}><Text style={styles.retryText}>Try again</Text></Pressable>
          </View>
        ) : (
          <View style={[styles.catalogBody, layout.isDesktop && !compact && styles.catalogBodyDesktop]}>
            {layout.isDesktop && !compact ? <View style={styles.sidebar}>{controls}</View> : null}
            <View style={styles.grid}>
              {visible.length ? visible.map((item) => (
                <View key={item.id} style={[styles.cell, gridCell(layout.productGridColumns)]}>
                  <ProductCard
                    product={item}
                    onOpen={() => router.push(`/product/${item.id}`)}
                    onAdd={() => {
                      if (cart.some((row) => row.productId === item.id)) {
                        router.push('/saved');
                        return;
                      }
                      void addToCart(item.id, { sourceType: 'product' });
                    }}
                    inCart={cart.some((row) => row.productId === item.id)}
                    onAskPicki={() => {
                      const request = openProductInPicki(item.id);
                      router.push('/');
                      void request.catch(() => undefined);
                    }}
                  />
                </View>
              )) : (
                <View style={styles.state}>
                  <Ionicons name="search-outline" size={28} color={colors.textSoft} />
                  <Text style={styles.stateTitle}>No matching products</Text>
                  <Text style={styles.stateText}>Try a broader search or reset the filters.</Text>
                </View>
              )}
            </View>
          </View>
        )}
      </ResponsiveContainer>

      <Modal visible={filtersOpen} transparent animationType="slide" onRequestClose={() => setFiltersOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setFiltersOpen(false)}>
          <Pressable style={[styles.sheet, { paddingBottom: Math.max(insets.bottom, spacing.lg) }]} onPress={() => undefined}>
            <View style={styles.handle} />
            <View style={styles.sheetHead}><Text style={styles.sheetTitle}>Filters and sorting</Text><Pressable onPress={() => setFiltersOpen(false)}><Ionicons name="close" size={22} color={colors.textPrimary} /></Pressable></View>
            <ScrollView style={styles.sheetScroll} contentContainerStyle={styles.sheetScrollContent} showsVerticalScrollIndicator={false}>
              {controls}
            </ScrollView>
            <Pressable onPress={() => setFiltersOpen(false)} style={styles.apply}><Text style={styles.applyText}>View {pageCount} products</Text></Pressable>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

function FilterControls({
  brands,
  brand,
  maxPrice,
  sort,
  onBrand,
  onMaxPrice,
  onSort,
  onReset,
}: {
  brands: string[];
  brand: string;
  maxPrice: number | null;
  sort: SortMode;
  onBrand: (value: string) => void;
  onMaxPrice: (value: number | null) => void;
  onSort: (value: SortMode) => void;
  onReset: () => void;
}) {
  return (
    <View style={styles.controls}>
      <View style={styles.controlHead}><Text style={styles.controlTitle}>Sort</Text><Pressable onPress={onReset}><Text style={styles.reset}>Reset</Text></Pressable></View>
      <View style={styles.options}>
        {([
          ['price_low', 'Price: low to high'],
          ['price_high', 'Price: high to low'],
          ['recommended', 'Recommended'],
          ['rating', 'Rating'],
          ['reviews', 'Review count'],
        ] as const).map(([value, label]) => <QuickFilter key={value} label={label} active={sort === value} onPress={() => onSort(value)} />)}
      </View>
      <Text style={styles.controlTitle}>Price</Text>
      <View style={styles.options}>
        {([[null, 'Any'], [25, 'Under $25'], [50, 'Under $50'], [100, 'Under $100'], [200, 'Under $200']] as const).map(([value, label]) => (
          <QuickFilter key={label} label={label} active={maxPrice === value} onPress={() => onMaxPrice(value)} />
        ))}
      </View>
      <Text style={styles.controlTitle}>Brand</Text>
      <View style={styles.options}>{brands.map((item) => <QuickFilter key={item} label={item} active={brand === item} onPress={() => onBrand(item)} />)}</View>
    </View>
  );
}

function QuickFilter({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return <Pressable onPress={onPress} style={[styles.quick, active && styles.quickActive]}><Text style={[styles.quickText, active && styles.quickTextActive]}>{label}</Text></Pressable>;
}

function gridCell(columns: number) {
  return { width: `${100 / columns}%` as `${number}%` };
}

const styles = StyleSheet.create({
  root: { width: '100%' },
  searchHeader: { flexDirection: 'row', gap: 8, paddingTop: 12, paddingHorizontal: 0 },
  searchHeaderDesktop: { paddingTop: 20, paddingHorizontal: 0 },
  search: { flex: 1, minHeight: 45, flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 24, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 16 },
  searchInput: { flex: 1, color: colors.textPrimary, fontSize: 14 },
  filterButton: { width: 46, height: 46, alignItems: 'center', justifyContent: 'center', borderRadius: radius.round, backgroundColor: colors.surface },
  mobileFiltersScroll: { flexGrow: 0, flexShrink: 0, height: 46, marginTop: 10 },
  mobileFilters: { alignItems: 'center', gap: 7, paddingRight: 12 },
  resultHead: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', paddingHorizontal: 0, paddingTop: 14, paddingBottom: 10 },
  resultTitle: { color: colors.textPrimary, fontSize: 18, fontWeight: '800' },
  resultCount: { marginTop: 2, color: colors.textSoft, fontSize: 11 },
  viewAll: { color: colors.brand, fontSize: 13, fontWeight: '900' },
  catalogBody: { flex: 1 },
  catalogBodyDesktop: { flexDirection: 'row', alignItems: 'flex-start', gap: 18, paddingHorizontal: 0 },
  sidebar: { width: 220, borderRadius: radius.md, backgroundColor: colors.surface, padding: spacing.md },
  controls: { gap: 12 },
  controlHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  controlTitle: { color: colors.textPrimary, fontSize: 13, fontWeight: '900' },
  reset: { color: colors.brand, fontSize: 11, fontWeight: '800' },
  options: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  quick: { alignSelf: 'flex-start', borderRadius: radius.round, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, paddingVertical: 8, paddingHorizontal: 11 },
  quickActive: { backgroundColor: colors.brandSoft, borderColor: '#FFC8AE' },
  quickText: { color: colors.textSecondary, fontSize: 11, fontWeight: '700' },
  quickTextActive: { color: colors.brand, fontWeight: '900' },
  grid: { flex: 1, flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -5 },
  cell: { minWidth: 0, paddingHorizontal: 5, marginBottom: 10 },
  state: { flex: 1, minHeight: 220, alignItems: 'center', justifyContent: 'center', padding: 24 },
  stateTitle: { marginTop: 8, color: colors.textPrimary, fontSize: 16, fontWeight: '900' },
  stateText: { marginTop: 5, color: colors.textSecondary, fontSize: 13, textAlign: 'center' },
  retry: { marginTop: 12, borderRadius: radius.md, backgroundColor: colors.brand, paddingVertical: 10, paddingHorizontal: 18 },
  retryText: { color: colors.white, fontSize: 13, fontWeight: '900' },
  backdrop: { flex: 1, justifyContent: 'flex-end', backgroundColor: colors.overlay },
  sheet: { maxHeight: '82%', borderTopLeftRadius: 18, borderTopRightRadius: 18, backgroundColor: colors.surface, padding: spacing.lg },
  sheetScroll: { flexGrow: 0 },
  sheetScrollContent: { paddingBottom: 8 },
  handle: { alignSelf: 'center', width: 38, height: 4, borderRadius: 2, backgroundColor: colors.border, marginBottom: 12 },
  sheetHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.lg },
  sheetTitle: { color: colors.textPrimary, fontSize: 19, fontWeight: '900' },
  apply: { marginTop: 20, alignItems: 'center', borderRadius: radius.md, backgroundColor: colors.brand, paddingVertical: 13 },
  applyText: { color: colors.white, fontSize: 14, fontWeight: '900' },
});
