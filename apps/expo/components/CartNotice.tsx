import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { productTitle } from '../lib/format';
import { usePickMate } from '../store/PickMateStore';
import { colors, radius, spacing } from '../theme';

export function CartNotice() {
  const { cartNotice, dismissCartNotice, getProduct, cart } = usePickMate();
  if (!cartNotice) return null;
  const product = getProduct(cartNotice.productId) || cart.find((item) => item.productId === cartNotice.productId)?.product;
  const name = product ? productTitle(product) : 'This product';
  return (
    <Modal visible transparent animationType="fade" onRequestClose={dismissCartNotice}>
      <Pressable style={styles.scrim} onPress={dismissCartNotice}>
        <Pressable style={styles.sheet} onPress={() => undefined}>
          <View style={styles.row}>
            <View style={styles.mark}><Ionicons name="checkmark" size={22} color={colors.success} /></View>
            <View style={{ flex: 1, gap: 4 }}>
              <Text style={styles.title}>{cartNotice.already ? 'Already in My Picks' : 'Saved to My Picks'}</Text>
              <Text style={styles.name} numberOfLines={2}>{name}</Text>
            </View>
            <Pressable onPress={dismissCartNotice}><Ionicons name="close" size={20} color={colors.textSecondary} /></Pressable>
          </View>
          <View style={styles.actions}>
            <Pressable onPress={dismissCartNotice} style={styles.ghost}><Text style={styles.ghostText}>Keep browsing</Text></Pressable>
            <Pressable onPress={() => { dismissCartNotice(); router.push('/saved'); }} style={styles.primary}><Text style={styles.primaryText}>View My Picks</Text></Pressable>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: { flex: 1, backgroundColor: colors.overlay, justifyContent: 'center', padding: spacing.lg },
  sheet: { alignSelf: 'center', width: '100%', maxWidth: 440, backgroundColor: colors.white, borderRadius: 20, padding: 26, gap: 22 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  mark: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.successSoft, alignItems: 'center', justifyContent: 'center' },
  title: { color: colors.textPrimary, fontSize: 19, fontWeight: '600' },
  name: { color: colors.textSecondary, fontSize: 12, lineHeight: 17 },
  actions: { flexDirection: 'row', gap: 10 },
  ghost: { flex: 1, minHeight: 46, alignItems: 'center', justifyContent: 'center', borderRadius: 10, borderWidth: 1, borderColor: colors.border },
  ghostText: { color: colors.textPrimary, fontSize: 13, fontWeight: '600' },
  primary: { flex: 1, minHeight: 46, alignItems: 'center', justifyContent: 'center', borderRadius: 10, backgroundColor: colors.brand },
  primaryText: { color: colors.white, fontSize: 13, fontWeight: '600' },
});
