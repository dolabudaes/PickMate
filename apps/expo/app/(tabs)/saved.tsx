import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { AppScreen } from '../../components/AppScreen';
import { MyTastePanel } from '../../components/MyTastePanel';
import { ActionButton } from '../../components/ProductChrome';
import { ProductVisual } from '../../components/ProductVisual';
import { RelatedChats } from '../../components/RelatedChats';
import { ResponsiveContainer } from '../../components/ResponsiveContainer';
import { useResponsiveLayout } from '../../components/responsive';
import { contentLineLimit, displayPrice, displaySpec, displayTitle } from '../../lib/format';
import { DEMO_MODE } from '../../lib/demo';
import { demoInitialSelectedProductIds } from '../../lib/navigation';
import { usePickMate } from '../../store/PickMateStore';
import { colors, spacing } from '../../theme';

export default function MyPicksScreen() {
  const layout = useResponsiveLayout();
  const {
    cart,
    cartSelected,
    shoppingMemories,
    memoryEnabled,
    toggleCartSelected,
    setCartSelected,
    compareSelection,
    removeSelectedFromCart,
    setMemoryEnabled,
    forgetShoppingMemory,
    saveShoppingPreference,
    confirmShoppingPreference,
    setShoppingPreferencePriority,
    dismissShoppingPreference,
  } = usePickMate();
  const initializedDemoSelection = useRef(false);
  const [buyLaterOpen, setBuyLaterOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const selectedItems = cart.filter((item) => cartSelected.includes(item.productId));
  const selectedTotal = selectedItems.reduce((sum, item) => sum + (item.price || 0), 0);
  const allSelected = cart.length > 0 && cartSelected.length === cart.length;
  const canCompare = cartSelected.length === 2;
  const tooMany = cartSelected.length > 2;

  useEffect(() => {
    if (!DEMO_MODE || initializedDemoSelection.current || cart.length < 3) return;
    const initial = demoInitialSelectedProductIds().filter((id) => cart.some((item) => item.productId === id));
    if (initial.length === 2) {
      initializedDemoSelection.current = true;
      setCartSelected(initial);
    }
  }, [cart, setCartSelected]);

  return (
    <AppScreen padded={false}>
      <ScrollView contentContainerStyle={{ paddingBottom: layout.isDesktop ? 64 : layout.tabBarHeight + 28 }}>
        <ResponsiveContainer maxWidth={1180}>
          <View style={layout.isDesktop ? styles.columns : [styles.stack, styles.stackMobile]}>
            <View style={layout.isDesktop ? styles.cartCol : styles.cartColMobile}>
              <View style={[styles.titleRow, layout.isMobile && styles.titleRowMobile]}>
                <Text style={[styles.title, layout.isMobile && styles.titleMobile]}>My Picks</Text>
                <View style={layout.isMobile ? styles.relatedMobile : undefined}>
                  <RelatedChats productIds={cart.map((item) => item.productId)} />
                </View>
              </View>
              <View style={[styles.sectionTitle, layout.isMobile && styles.sectionTitleMobile]}>
                <Text style={styles.sectionHeading}>Saved candidates</Text>
                {cart.length ? <Pressable onPress={() => setCartSelected(allSelected ? [] : cart.map((item) => item.productId))}><Text style={styles.link}>{allSelected ? 'Clear selection' : 'Select all'}</Text></Pressable> : null}
              </View>
              {cart.length ? cart.map((item) => {
                const selected = cartSelected.includes(item.productId);
                return (
                  <Pressable
                    key={item.id}
                    style={({ hovered, pressed }) => [styles.line, layout.isMobile && styles.lineMobile, (hovered || pressed) && styles.lineHover]}
                    onPress={() => router.push(`/product/${item.productId}`)}
                  >
                    <Pressable
                      accessibilityRole="checkbox"
                      accessibilityLabel={`Select ${item.product ? displayTitle(item.product) : item.title}`}
                      accessibilityState={{ checked: selected }}
                      onPress={(event) => { event.stopPropagation(); toggleCartSelected(item.productId); }}
                      style={[styles.check, layout.isMobile && styles.checkMobile, selected && styles.checkOn]}
                    >
                      {selected ? <Ionicons name="checkmark" size={12} color={colors.white} /> : null}
                    </Pressable>
                    <View style={[styles.thumb, layout.isMobile && styles.thumbMobile]}>{item.product ? <ProductVisual product={item.product} size={layout.isMobile ? 52 : 64} /> : null}</View>
                    <View style={styles.lineCopy}>
                      <Text style={[styles.name, layout.isMobile && styles.nameMobile]} numberOfLines={contentLineLimit(layout.isMobile, 2)}>{item.product ? displayTitle(item.product) : item.title}</Text>
                      {item.product && displaySpec(item.product) ? <Text style={[styles.spec, layout.isMobile && styles.specMobile]} numberOfLines={contentLineLimit(layout.isMobile, 1)}>{displaySpec(item.product)}</Text> : null}
                      <Text style={[styles.price, layout.isMobile && styles.priceMobile]}>{item.product ? displayPrice(item.product) : item.price != null ? `$${item.price.toFixed(2)}` : 'Price unavailable'}</Text>
                    </View>
                  </Pressable>
                );
              }) : (
                <View style={styles.emptyCart}>
                  <Text style={styles.emptyTitle}>My Picks is empty</Text>
                  <Text style={styles.emptyCopy}>Save candidates from Explore or a Picki recommendation and they will appear here.</Text>
                  <Pressable onPress={() => router.push('/explore')} style={styles.primary}><Text style={styles.primaryText}>Explore products</Text></Pressable>
                </View>
              )}
              <View style={layout.isNarrowPhone ? styles.cartBottomStack : styles.cartBottom}>
                <View style={styles.selectionSummary}>
                  <Text style={styles.ref}>{selectedItems.length} selected · ${selectedTotal.toFixed(2)}</Text>
                  {tooMany ? <Text style={styles.hint}>Select exactly two products for a focused comparison.</Text> : null}
                </View>
                <View style={styles.cartActions}>
                  <ActionButton label="Compare with Picki" icon="git-compare-outline" onPress={() => { void compareSelection(); }} disabled={!canCompare} />
                  <ActionButton label="Remove" icon="trash-outline" variant="ghost" onPress={() => setDeleteOpen(true)} disabled={!cartSelected.length} />
                  <ActionButton label="Buy later" icon="time-outline" variant="secondary" onPress={() => setBuyLaterOpen(true)} disabled={!cartSelected.length} />
                </View>
              </View>
            </View>
            <View nativeID="taste" style={layout.isDesktop ? styles.tasteCol : styles.tasteColMobile}>
              <MyTastePanel
                compact
                memories={shoppingMemories}
                memoryEnabled={memoryEnabled}
                onToggleMemory={(value) => { void setMemoryEnabled(value); }}
                onForget={(id) => { void forgetShoppingMemory(id); }}
                onSavePreference={saveShoppingPreference}
                onConfirmPreference={confirmShoppingPreference}
                onSetPriority={setShoppingPreferencePriority}
                onDismissPreference={dismissShoppingPreference}
              />
            </View>
          </View>
        </ResponsiveContainer>
      </ScrollView>
      <Modal visible={buyLaterOpen} transparent animationType="fade" onRequestClose={() => setBuyLaterOpen(false)}>
        <Pressable style={styles.scrim} onPress={() => setBuyLaterOpen(false)}>
          <Pressable style={styles.dialog} onPress={() => undefined}>
            <Text style={styles.dialogTitle}>Saved for later</Text>
            <Text style={styles.dialogCopy}>These products will stay in My Picks. No order or payment has been created.</Text>
            <Pressable onPress={() => setBuyLaterOpen(false)} style={styles.primary}><Text style={styles.primaryText}>Back to My Picks</Text></Pressable>
          </Pressable>
        </Pressable>
      </Modal>
      <Modal visible={deleteOpen} transparent animationType="fade" onRequestClose={() => setDeleteOpen(false)}>
        <Pressable style={styles.scrim} onPress={() => setDeleteOpen(false)}>
          <Pressable style={styles.dialog} onPress={() => undefined}>
            <Text style={styles.dialogTitle}>Remove selected products?</Text>
            <Text style={styles.dialogCopy}>This will remove {cartSelected.length} products from My Picks. The original conversation will remain available.</Text>
            <View style={styles.dialogActions}>
              <Pressable onPress={() => setDeleteOpen(false)} style={styles.actionGhost}>
                <Text style={styles.actionGhostText}>Cancel</Text>
              </Pressable>
              <Pressable onPress={() => { setDeleteOpen(false); void removeSelectedFromCart(); }} style={styles.actionPrimary}>
                <Text style={styles.actionPrimaryText}>Remove</Text>
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      </Modal>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  columns: { flexDirection: 'row', alignItems: 'flex-start', gap: 32, paddingHorizontal: spacing.md, paddingTop: spacing.lg },
  stack: { gap: 24, paddingHorizontal: spacing.md, paddingTop: spacing.lg },
  stackMobile: { gap: 16, paddingHorizontal: 12, paddingTop: 12 },
  cartCol: { flex: 1.5, minWidth: 0 },
  cartColMobile: { width: '100%', minWidth: 0 },
  tasteCol: { flex: 1, minWidth: 300 },
  tasteColMobile: { width: '100%', minWidth: 0 },
  title: { color: colors.textPrimary, fontSize: 30, fontWeight: '700', letterSpacing: -0.8 },
  titleMobile: { fontSize: 25, letterSpacing: -0.5 },
  titleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  titleRowMobile: { flexWrap: 'wrap' },
  relatedMobile: { width: '100%', zIndex: 10, marginTop: -38 },
  sectionTitle: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 16, marginBottom: 4 },
  sectionTitleMobile: { marginTop: 10, marginBottom: 2 },
  sectionHeading: { color: colors.textPrimary, fontSize: 16, fontWeight: '700' },
  link: { color: colors.textSecondary, fontSize: 12, fontWeight: '600' },
  line: { flexDirection: 'row', gap: 12, alignItems: 'flex-start', borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, paddingVertical: 12 },
  lineMobile: { gap: 9, paddingVertical: 8 },
  lineHover: { backgroundColor: '#FFFBF8' },
  check: { width: 18, height: 18, marginTop: 22, borderRadius: 5, borderWidth: 1.5, borderColor: '#CFC9C3', alignItems: 'center', justifyContent: 'center' },
  checkMobile: { marginTop: 17 },
  checkOn: { backgroundColor: colors.brand, borderColor: colors.brand },
  thumb: { width: 64, height: 64, borderRadius: 10, overflow: 'hidden', backgroundColor: '#F8F8F7' },
  thumbMobile: { width: 52, height: 52, borderRadius: 8 },
  lineCopy: { flex: 1, minWidth: 0 },
  name: { color: colors.textPrimary, fontSize: 16, fontWeight: '700', lineHeight: 20 },
  nameMobile: { fontSize: 14, lineHeight: 18 },
  spec: { marginTop: 3, color: colors.textSecondary, fontSize: 13 },
  specMobile: { marginTop: 1, fontSize: 11 },
  price: { marginTop: 4, color: colors.textPrimary, fontSize: 16, fontWeight: '700' },
  priceMobile: { marginTop: 2, fontSize: 14 },
  ref: { color: '#9D9893', fontSize: 12 },
  hint: { marginTop: 4, color: colors.textSecondary, fontSize: 13 },
  scrim: { flex: 1, backgroundColor: colors.overlay, justifyContent: 'center', padding: spacing.lg },
  dialog: { alignSelf: 'center', width: '100%', maxWidth: 420, backgroundColor: colors.white, borderRadius: 18, padding: 24, gap: 12 },
  dialogTitle: { color: colors.textPrimary, fontSize: 20, fontWeight: '600' },
  dialogCopy: { color: colors.textSecondary, fontSize: 14, lineHeight: 21 },
  selectionSummary: { flexShrink: 1, minWidth: 110 },
  cartActions: { flex: 1, minWidth: 0, flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'flex-end', gap: 8 },
  dialogActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8, marginTop: 8 },
  actionPrimary: { minHeight: 34, borderRadius: 9, backgroundColor: colors.brand, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 12 },
  actionPrimaryText: { color: colors.white, fontSize: 12, fontWeight: '700' },
  actionGhost: { minHeight: 34, borderRadius: 9, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 10 },
  actionGhostText: { color: colors.textPrimary, fontSize: 12, fontWeight: '700' },
  emptyCart: { minHeight: 160, alignItems: 'flex-start', justifyContent: 'center', paddingVertical: 20, gap: 8 },
  emptyTitle: { color: colors.textPrimary, fontSize: 16, fontWeight: '700' },
  emptyCopy: { color: colors.textSecondary, fontSize: 13, lineHeight: 19 },
  cartBottom: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, paddingTop: 14, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 12 },
  cartBottomStack: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, paddingTop: 14, gap: 12 },
  primary: { minHeight: 40, borderRadius: 10, backgroundColor: colors.brand, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 16, alignSelf: 'flex-start' },
  primaryText: { color: colors.white, fontSize: 13, fontWeight: '700' },
});
