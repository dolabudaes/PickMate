import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useEffect } from 'react';
import { BackHandler, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { productTitle } from '../lib/format';
import { usePickMate } from '../store/PickMateStore';
import { colors, spacing } from '../theme';
import { PickiConversation } from './PickiConversation';
import { useResponsiveLayout } from './responsive';

export function AskPickiHost() {
  const layout = useResponsiveLayout();
  const { pickiOpen, closeQuickTake, pickiProductId, getProduct, openFullChat, pickiWorkspaceActive } = usePickMate();
  const product = pickiProductId ? getProduct(pickiProductId) : undefined;

  useEffect(() => {
    if (!pickiOpen || layout.isDesktop) return;
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      closeQuickTake();
      return true;
    });
    return () => sub.remove();
  }, [closeQuickTake, layout.isDesktop, pickiOpen]);

  if (!pickiOpen || pickiWorkspaceActive) return null;

  if (!layout.isDesktop) {
    return (
      <View style={styles.mobileOverlay} accessibilityViewIsModal>
        <SafeAreaView style={styles.mobile} edges={['top', 'left', 'right', 'bottom']}>
          <View style={styles.sheetHead}>
            <Pressable accessibilityLabel="Close" onPress={closeQuickTake} style={styles.sheetBtn} hitSlop={8}>
              <Ionicons name="chevron-down" size={24} color={colors.textPrimary} />
            </Pressable>
            <View style={styles.sheetTitleWrap}>
              <Text style={styles.sheetTitle}>Ask Picki</Text>
              {product ? (
                <Text style={styles.sheetSubtitle} numberOfLines={1}>{productTitle(product)}</Text>
              ) : null}
            </View>
            <Pressable
              accessibilityLabel="Open full conversation"
              onPress={() => { openFullChat(); closeQuickTake(); router.push('/'); }}
              style={styles.sheetBtn}
              hitSlop={8}
            >
              <Text style={styles.sheetAction}>Open</Text>
            </Pressable>
          </View>
          <View style={styles.sheetBody}>
            <PickiConversation mode="drawer" sheet showHeader={false} onClose={closeQuickTake} />
          </View>
        </SafeAreaView>
      </View>
    );
  }

  return (
    <View pointerEvents="box-none" style={StyleSheet.absoluteFill}>
      <Pressable style={styles.scrim} onPress={closeQuickTake} />
      <View style={styles.drawer}>
        <View style={styles.drawerHead}>
          <Text style={styles.drawerLabel}>Ask Picki</Text>
          <Pressable onPress={closeQuickTake} hitSlop={8}><Text style={styles.close}>Close</Text></Pressable>
        </View>
        <PickiConversation mode="drawer" onClose={closeQuickTake} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  mobileOverlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 2000,
    elevation: 2000,
    backgroundColor: colors.white,
    overflow: 'hidden',
  },
  scrim: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(24,20,16,0.26)' },
  drawer: { position: 'absolute', top: 0, right: 0, bottom: 0, width: 520, maxWidth: '100%', backgroundColor: colors.white, zIndex: 40 },
  mobile: { flex: 1, width: '100%', maxWidth: '100%', minHeight: 0, backgroundColor: colors.white },
  sheetHead: {
    minHeight: 52,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    gap: 8,
  },
  sheetBtn: { minWidth: 52, minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  sheetTitleWrap: { flex: 1, minWidth: 0, alignItems: 'center' },
  sheetTitle: { color: colors.textPrimary, fontSize: 15, fontWeight: '800' },
  sheetSubtitle: { marginTop: 2, color: colors.textSoft, fontSize: 11, maxWidth: '100%' },
  sheetAction: { color: colors.brand, fontSize: 13, fontWeight: '700' },
  sheetBody: { flex: 1, minHeight: 0, width: '100%' },
  drawerHead: {
    height: 52,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
  },
  drawerLabel: { color: colors.textSecondary, fontSize: 12, fontWeight: '700' },
  close: { color: colors.textPrimary, fontSize: 13, fontWeight: '700' },
});
