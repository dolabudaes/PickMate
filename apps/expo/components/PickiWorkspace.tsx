import { Ionicons } from '@expo/vector-icons';
import { useEffect, useState } from 'react';
import { Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { conversationDisplayTitle, DEMO_MODE, orderDemoConversations } from '../lib/demo';
import { chatExamples } from '../lib/examples';
import { usePickMate } from '../store/PickMateStore';
import { colors, radius, spacing } from '../theme';
import { PickiConversation } from './PickiConversation';
import { useResponsiveLayout } from './responsive';
import { conversationHistorySurface } from '../lib/navigation';

export function PickiWorkspace() {
  const layout = useResponsiveLayout();
  const { conversations, activeConversationId, runningDecision, startNewConversation, renameConversation, deleteConversation, selectConversation, openPickiFind, setPickiWorkspaceActive } = usePickMate();
  const [listOpen, setListOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const visibleChats = DEMO_MODE ? orderDemoConversations(conversations) : conversations;
  const historySurface = conversationHistorySurface(Platform.OS, layout.isDesktop);

  useEffect(() => {
    setPickiWorkspaceActive(true);
    return () => setPickiWorkspaceActive(false);
  }, [setPickiWorkspaceActive]);

  const conversationRail = (
        <View style={[styles.rail, layout.isDesktop ? styles.railDesktop : styles.railMobileModal]}>
          <View style={styles.railBrand}>
            <View style={styles.railMark}>
              <Ionicons name="sparkles" size={17} color={colors.white} />
            </View>
            <View style={styles.railBrandCopy}>
              <Text style={styles.railBrandTitle}>Picki</Text>
            </View>
            {!layout.isDesktop ? (
              <Pressable accessibilityLabel="Close conversation history" onPress={() => setListOpen(false)} style={styles.mobileClose}>
                <Ionicons name="close" size={22} color={colors.textPrimary} />
              </Pressable>
            ) : null}
          </View>
          <View style={styles.railHead}>
            <Pressable accessibilityLabel="New conversation" accessibilityState={{ disabled: runningDecision }} disabled={runningDecision} onPress={() => { void startNewConversation(); setListOpen(false); }} style={[styles.newChat, runningDecision && styles.disabled]}>
                <Ionicons name="add" size={17} color={colors.white} />
                <Text style={styles.newChatText}>New conversation</Text>
              </Pressable>
          </View>
          <ScrollView style={styles.railList}>
            {visibleChats.length ? visibleChats.map((item) => {
              const active = item.id === activeConversationId;
              const displayTitle = conversationDisplayTitle(item);
              return (
                <View key={item.id} style={[styles.item, active && styles.itemActive]}>
                  {editingId === item.id ? (
                    <TextInput
                      autoFocus
                      value={editingTitle}
                      onChangeText={setEditingTitle}
                      onBlur={() => { void renameConversation(item.id, editingTitle); setEditingId(null); }}
                      onSubmitEditing={() => { void renameConversation(item.id, editingTitle); setEditingId(null); }}
                      style={styles.renameInput}
                    />
                  ) : (
                    <Pressable accessibilityState={{ disabled: runningDecision }} disabled={runningDecision} onPress={() => { void selectConversation(item.id); setListOpen(false); }} style={styles.itemCopy}>
                      <View style={styles.itemTopline}>
                        <Text style={[styles.itemTitle, active && styles.itemTitleActive]} numberOfLines={2}>{displayTitle}</Text>
                        {active ? <View style={styles.activeDot} /> : null}
                      </View>
                    </Pressable>
                  )}
                  {confirmDeleteId === item.id ? (
                    <View style={styles.itemActions}>
                      <Pressable accessibilityLabel="Cancel deletion" onPress={() => setConfirmDeleteId(null)} style={styles.confirmCancel}>
                        <Text style={styles.confirmCancelText}>Cancel</Text>
                      </Pressable>
                      <Pressable accessibilityLabel="Delete conversation" onPress={() => { setConfirmDeleteId(null); void deleteConversation(item.id); }} style={styles.confirmDelete}>
                        <Text style={styles.confirmDeleteText}>Delete</Text>
                      </Pressable>
                    </View>
                  ) : (
                    <View style={styles.itemActions}>
                      <Pressable accessibilityLabel="Rename conversation" accessibilityState={{ disabled: runningDecision }} disabled={runningDecision} onPress={() => { setEditingId(item.id); setEditingTitle(displayTitle); }} style={[styles.itemAction, runningDecision && styles.disabled]}>
                        <Ionicons name="pencil-outline" size={14} color={colors.textSecondary} />
                      </Pressable>
                      <Pressable accessibilityLabel="Delete conversation" accessibilityState={{ disabled: runningDecision }} disabled={runningDecision} onPress={() => setConfirmDeleteId(item.id)} style={[styles.itemAction, runningDecision && styles.disabled]}>
                        <Ionicons name="trash-outline" size={14} color={colors.textSecondary} />
                      </Pressable>
                    </View>
                  )}
                </View>
              );
            }) : (
              <View style={styles.examples}>
                {chatExamples.map((item) => (
                  <Pressable key={item.prompt} onPress={() => { setListOpen(false); openPickiFind(item.prompt); }} style={styles.example}>
                    <Text style={styles.itemTitle}>{item.label}</Text>
                  </Pressable>
                ))}
              </View>
            )}
          </ScrollView>
        </View>
  );

  return (
    <View style={[styles.root, layout.isDesktop && styles.rootDesktop]}>
      {historySurface === 'rail' ? conversationRail : historySurface === 'inline' ? (
        listOpen ? <View style={styles.inlineHistory}>{conversationRail}</View> : null
      ) : (
        <Modal visible={listOpen} animationType="slide" presentationStyle="fullScreen" onRequestClose={() => setListOpen(false)}>
          <SafeAreaView edges={['top', 'bottom', 'left', 'right']} style={styles.modalSafe}>
            {conversationRail}
          </SafeAreaView>
        </Modal>
      )}
      <View style={styles.main}>
        <PickiConversation embedded onOpenChats={layout.isDesktop ? undefined : () => setListOpen((value) => !value)} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#FCFBF9' },
  rootDesktop: { flexDirection: 'row', padding: 10, gap: 10 },
  inlineHistory: { ...StyleSheet.absoluteFillObject, zIndex: 40, backgroundColor: colors.surface },
  rail: { width: '100%', maxHeight: 340, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border, backgroundColor: '#FBFAF8', paddingBottom: 10 },
  railDesktop: { width: 270, maxHeight: '100%', borderWidth: 1, borderColor: colors.border, borderRadius: 16, backgroundColor: '#F8F6F3', overflow: 'hidden' },
  railMobileModal: { flex: 1, maxHeight: '100%', paddingBottom: 0, backgroundColor: colors.surface },
  modalSafe: { flex: 1, backgroundColor: colors.surface },
  railList: { flex: 1 },
  railBrand: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: spacing.lg, paddingTop: spacing.lg, paddingBottom: spacing.md },
  railMark: { width: 36, height: 36, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.brand },
  railBrandCopy: { flex: 1, minWidth: 0 },
  railBrandTitle: { color: colors.textPrimary, fontSize: 16, fontWeight: '900', letterSpacing: -0.2 },
  mobileClose: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center', borderRadius: radius.round },
  railHead: { paddingHorizontal: spacing.lg, paddingBottom: 10 },
  newChat: { minHeight: 42, flexDirection: 'row', gap: 6, alignItems: 'center', justifyContent: 'center', borderRadius: 11, backgroundColor: colors.brand },
  newChatText: { color: colors.white, fontSize: 14, fontWeight: '800' },
  disabled: { opacity: 0.45 },
  item: { flexDirection: 'row', alignItems: 'center', marginHorizontal: 8, marginBottom: 4, borderRadius: 12, paddingLeft: spacing.md, paddingRight: 6, paddingVertical: 8, borderWidth: 1, borderColor: 'transparent' },
  itemCopy: { flex: 1, minWidth: 0, paddingVertical: 3 },
  itemActive: { borderColor: '#F2D9CC', backgroundColor: '#FFF7F2' },
  itemTopline: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  itemTitle: { flex: 1, color: '#4D4945', fontSize: 13, lineHeight: 18, fontWeight: '700' },
  itemTitleActive: { color: colors.textPrimary, fontWeight: '800' },
  activeDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.brand },
  itemActions: { flexDirection: 'row', alignItems: 'center' },
  itemAction: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  confirmCancel: { minHeight: 44, justifyContent: 'center', paddingHorizontal: 10 },
  confirmCancelText: { color: colors.textSecondary, fontSize: 11, fontWeight: '700' },
  confirmDelete: { minHeight: 44, justifyContent: 'center', borderRadius: 9, backgroundColor: '#9B2C2C', paddingHorizontal: 12 },
  confirmDeleteText: { color: colors.white, fontSize: 11, fontWeight: '800' },
  renameInput: { flex: 1, minHeight: 38, borderRadius: 8, borderWidth: 1, borderColor: colors.brand, backgroundColor: colors.white, color: colors.textPrimary, paddingHorizontal: 9, fontSize: 13 },
  examples: { gap: 4, paddingBottom: 8 },
  example: { paddingHorizontal: spacing.md, paddingVertical: 8 },
  main: { flex: 1, minHeight: 0, overflow: 'hidden', backgroundColor: colors.white },
});
