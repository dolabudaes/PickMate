import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { usePickMate } from '../store/PickMateStore';
import { conversationDisplayTitle } from '../lib/demo';
import { colors, radius, spacing } from '../theme';
import { relatedChatsSurface } from '../lib/navigation';
import { useResponsiveLayout } from './responsive';

export function RelatedChats({ productIds }: { productIds: string[] }) {
  const { relatedChatsForProducts, selectConversation } = usePickMate();
  const layout = useResponsiveLayout();
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<Awaited<ReturnType<typeof relatedChatsForProducts>>>([]);

  async function show() {
    setRows(await relatedChatsForProducts(productIds).catch(() => []));
    setOpen(true);
  }

  function openChat(id: string) {
    setOpen(false);
    void selectConversation(id);
    router.push('/');
  }

  const inline = relatedChatsSurface(layout.isMobile) === 'inline';
  const trigger = (
      <Pressable onPress={() => { void show(); }} style={[styles.trigger, inline && styles.triggerMobile]}>
        <Ionicons name="chatbubbles-outline" size={16} color={colors.brand} />
        <Text style={styles.triggerText}>Related chats</Text>
      </Pressable>
  );
  const panel = (
    <View style={[styles.sheet, inline && styles.sheetInline]}>
      <View style={styles.head}>
        <Text style={[styles.title, inline && styles.titleMobile]}>Related chats</Text>
        <Pressable accessibilityLabel="Close related chats" onPress={() => setOpen(false)} style={styles.close}>
          <Ionicons name="close" size={20} color={colors.textPrimary} />
        </Pressable>
      </View>
      <ScrollView style={inline ? styles.rowsMobile : undefined} showsVerticalScrollIndicator={false}>
        {rows.length ? rows.map((item) => (
          <Pressable key={item.id} onPress={() => openChat(item.id)} style={[styles.row, inline && styles.rowMobile]}>
            <View style={styles.rowCopy}>
              <Text style={[styles.rowTitle, inline && styles.rowTitleMobile]}>{conversationDisplayTitle(item)}</Text>
              <Text style={styles.rowCount}>{item.relatedProductCount ?? 0} related products</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={colors.textSoft} />
          </Pressable>
        )) : (
          <View style={styles.empty}>
            <Text style={styles.emptyText}>No related chats yet.</Text>
          </View>
        )}
      </ScrollView>
    </View>
  );

  if (inline) {
    return (
      <View style={styles.inlineHost}>
        {trigger}
        {open ? panel : null}
      </View>
    );
  }

  return (
    <>
      {trigger}
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.scrim} onPress={() => setOpen(false)}>
          <Pressable style={styles.modalPanel} onPress={() => undefined}>{panel}</Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  inlineHost: { width: '100%', alignItems: 'stretch', gap: 6 },
  trigger: { minHeight: 36, flexDirection: 'row', alignItems: 'center', gap: 6, justifyContent: 'center', borderRadius: radius.round, borderWidth: 1, borderColor: '#E7D8CF', paddingHorizontal: 12 },
  triggerMobile: { minHeight: 32, alignSelf: 'flex-end', paddingHorizontal: 10 },
  triggerText: { color: colors.brand, fontSize: 13, fontWeight: '700' },
  scrim: { flex: 1, backgroundColor: 'rgba(28,32,36,0.42)', justifyContent: 'center', padding: spacing.lg },
  modalPanel: { maxWidth: 460, width: '100%', alignSelf: 'center' },
  sheet: { backgroundColor: colors.white, borderRadius: radius.lg, padding: spacing.lg, gap: 8, width: '100%' },
  sheetInline: { maxWidth: '100%', borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 10, gap: 4 },
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  title: { color: colors.textPrimary, fontSize: 18, fontWeight: '800' },
  titleMobile: { fontSize: 16 },
  close: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  rowsMobile: { maxHeight: 210 },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12, paddingVertical: 12, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  rowMobile: { minHeight: 50, paddingVertical: 7 },
  rowCopy: { flex: 1, minWidth: 0, gap: 3 },
  rowTitle: { flex: 1, color: colors.textPrimary, fontSize: 14, fontWeight: '700' },
  rowTitleMobile: { fontSize: 13 },
  rowCount: { color: colors.textSecondary, fontSize: 12 },
  empty: { gap: 12, paddingVertical: 8 },
  emptyText: { color: colors.textSecondary, fontSize: 13, lineHeight: 18 },
});
