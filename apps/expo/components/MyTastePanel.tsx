import { Ionicons } from '@expo/vector-icons';
import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import type { ShoppingMemory } from '../lib/shoppingTurn';
import { usePickMate } from '../store/PickMateStore';
import { colors, radius } from '../theme';
import { partitionTasteMemories, preferenceDisplayLabel } from '../lib/tasteInsights';
import { useResponsiveLayout } from './responsive';

export function MyTastePanel({
  memories,
  memoryEnabled,
  onToggleMemory,
  onForget,
  onSavePreference,
  onSetPriority,
  onConfirmPreference,
  onDismissPreference,
}: {
  compact?: boolean;
  memories: ShoppingMemory[];
  memoryEnabled: boolean;
  onToggleMemory: (enabled: boolean) => void;
  onForget: (id: string) => void;
  onSavePreference: (id: string, label: string) => Promise<void>;
  onConfirmPreference: (id: string) => Promise<void>;
  onSetPriority: (id: string, priority: number) => Promise<void>;
  onDismissPreference: (id: string) => Promise<void>;
}) {
  const { addTaste } = usePickMate();
  const layout = useResponsiveLayout();
  const [editing, setEditing] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [newPreference, setNewPreference] = useState('');
  const [busy, setBusy] = useState(false);

  const { confirmed, pending } = useMemo(() => partitionTasteMemories(memories), [memories]);

  function toggleEditing() {
    if (!editing) setDrafts(Object.fromEntries(confirmed.map((item) => [item.id, preferenceLabel(item)])));
    setEditing((value) => !value);
  }

  async function renamePreference(item: ShoppingMemory) {
    const next = (drafts[item.id] ?? preferenceLabel(item)).trim();
    if (!next || next === preferenceLabel(item)) return;
    setBusy(true);
    try {
      await onSavePreference(item.id, next);
    } finally {
      setBusy(false);
    }
  }

  async function addPreference() {
    const next = newPreference.trim();
    if (!next) return;
    setBusy(true);
    try {
      await addTaste(next);
      setNewPreference('');
    } finally {
      setBusy(false);
    }
  }

  async function resolvePending(id: string, action: 'confirm' | 'dismiss') {
    setBusy(true);
    try {
      if (action === 'confirm') await onConfirmPreference(id);
      else await onDismissPreference(id);
    } finally {
      setBusy(false);
    }
  }

  function movePreference(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= confirmed.length) return;
    const ordered = [...confirmed];
    [ordered[index], ordered[target]] = [ordered[target], ordered[index]];
    const step = 100 / Math.max(1, ordered.length - 1);
    void Promise.all(ordered.map((item, itemIndex) => onSetPriority(item.id, Math.max(0, Math.round(100 - itemIndex * step)))));
  }

  return (
    <View style={[styles.shell, !layout.isDesktop && styles.shellMobile]}>
      <View style={styles.header}>
        <Text style={[styles.title, !layout.isDesktop && styles.titleMobile]}>My Taste</Text>
        <View style={styles.headerActions}>
          <Pressable onPress={toggleEditing} style={styles.editMode}>
            <Text style={styles.editModeText}>{editing ? 'Done' : 'Edit'}</Text>
          </Pressable>
          <Switch accessibilityLabel="Personalization" value={memoryEnabled} onValueChange={onToggleMemory} trackColor={{ true: '#F4B996', false: '#E5E1DD' }} thumbColor={memoryEnabled ? colors.brand : colors.white} />
        </View>
      </View>

      <View style={[styles.bubbleWrap, !memoryEnabled && styles.muted]}>
        {confirmed.map((item, index) => editing ? (
          <View key={item.id} style={styles.editBubble}>
            <TextInput
              accessibilityLabel={`Rename preference ${index + 1}`}
              value={drafts[item.id] ?? preferenceLabel(item)}
              onChangeText={(value) => setDrafts((current) => ({ ...current, [item.id]: value }))}
              onEndEditing={() => { void renamePreference(item); }}
              blurOnSubmit
              returnKeyType="done"
              style={styles.editInput}
            />
            <Pressable accessibilityLabel={`Move ${preferenceLabel(item)} left`} disabled={index === 0 || busy} onPress={() => movePreference(index, -1)} style={[styles.iconButton, index === 0 && styles.disabled]}>
              <Ionicons name="chevron-back" size={16} color={colors.textSecondary} />
            </Pressable>
            <Pressable accessibilityLabel={`Move ${preferenceLabel(item)} right`} disabled={index === confirmed.length - 1 || busy} onPress={() => movePreference(index, 1)} style={[styles.iconButton, index === confirmed.length - 1 && styles.disabled]}>
              <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
            </Pressable>
            <Pressable accessibilityLabel={`Remove preference ${preferenceLabel(item)}`} disabled={busy} onPress={() => onForget(item.id)} style={styles.iconButton}>
              <Ionicons name="close" size={17} color={colors.textSecondary} />
            </Pressable>
          </View>
        ) : (
          <View key={item.id} style={[styles.bubble, !layout.isDesktop && styles.bubbleMobile]}>
            <Text style={[styles.bubbleText, !layout.isDesktop && styles.bubbleTextMobile]}>{preferenceLabel(item)}</Text>
          </View>
        ))}
      </View>

      {!editing && pending.length ? (
        <View style={[styles.pendingWrap, !memoryEnabled && styles.muted]}>
          {pending.map((item) => (
            <View key={item.id} style={[styles.pendingBubble, !layout.isDesktop && styles.pendingBubbleMobile]}>
              <Text style={[styles.pendingText, !layout.isDesktop && styles.pendingTextMobile]}>{preferenceLabel(item)}</Text>
              <View style={styles.pendingActions}>
                <Pressable disabled={busy} onPress={() => { void resolvePending(item.id, 'confirm'); }} style={styles.confirmAction}>
                  <Text style={styles.confirmActionText}>Confirm</Text>
                </Pressable>
                <Pressable disabled={busy} onPress={() => { void resolvePending(item.id, 'dismiss'); }} style={styles.dismissAction}>
                  <Text style={styles.dismissActionText}>Dismiss</Text>
                </Pressable>
              </View>
            </View>
          ))}
        </View>
      ) : null}

      {editing ? (
        <View style={styles.addRow}>
          <TextInput
            accessibilityLabel="Add preference"
            placeholder="Add preference"
            placeholderTextColor={colors.textSoft}
            value={newPreference}
            onChangeText={setNewPreference}
            onSubmitEditing={() => { void addPreference(); }}
            returnKeyType="done"
            style={styles.addInput}
          />
          <Pressable accessibilityLabel="Add preference" disabled={busy || !newPreference.trim()} onPress={() => { void addPreference(); }} style={[styles.addButton, (busy || !newPreference.trim()) && styles.disabled]}>
            <Ionicons name="add" size={18} color={colors.white} />
            <Text style={styles.addButtonText}>Add</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

function preferenceLabel(item: ShoppingMemory) {
  return preferenceDisplayLabel(item);
}

const styles = StyleSheet.create({
  shell: { gap: 14, borderLeftWidth: StyleSheet.hairlineWidth, borderLeftColor: colors.border, paddingLeft: 28 },
  shellMobile: { gap: 10, borderLeftWidth: 0, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, paddingLeft: 0, paddingTop: 14 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  title: { color: colors.textPrimary, fontSize: 25, fontWeight: '800', letterSpacing: -0.6 },
  titleMobile: { fontSize: 22, letterSpacing: -0.4 },
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  editMode: { minHeight: 34, justifyContent: 'center', paddingHorizontal: 6 },
  editModeText: { color: colors.brand, fontSize: 14, fontWeight: '700' },
  bubbleWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  bubble: { borderRadius: radius.round, borderWidth: 1, borderColor: '#E8DED6', backgroundColor: '#F8F4F0', paddingHorizontal: 18, paddingVertical: 11 },
  bubbleMobile: { paddingHorizontal: 12, paddingVertical: 7 },
  bubbleText: { color: colors.textPrimary, fontSize: 16, lineHeight: 22, fontWeight: '600' },
  bubbleTextMobile: { fontSize: 14, lineHeight: 19 },
  pendingWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  pendingBubble: { maxWidth: '100%', flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 8, borderRadius: radius.round, borderWidth: 1, borderColor: '#E5DED7', backgroundColor: colors.white, paddingLeft: 16, paddingRight: 7, paddingVertical: 7 },
  pendingBubbleMobile: { gap: 5, paddingLeft: 12, paddingVertical: 5 },
  pendingText: { color: colors.textPrimary, fontSize: 16, lineHeight: 22, fontWeight: '600' },
  pendingTextMobile: { fontSize: 14, lineHeight: 19 },
  pendingActions: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  confirmAction: { borderRadius: radius.round, backgroundColor: colors.brandSoft, paddingHorizontal: 10, paddingVertical: 6 },
  confirmActionText: { color: colors.brandInk, fontSize: 13, fontWeight: '700' },
  dismissAction: { borderRadius: radius.round, paddingHorizontal: 8, paddingVertical: 6 },
  dismissActionText: { color: colors.textSecondary, fontSize: 13, fontWeight: '600' },
  editBubble: { maxWidth: '100%', minHeight: 44, flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', borderRadius: radius.lg, borderWidth: 1, borderColor: '#E3C7B5', backgroundColor: '#FFF8F3', paddingLeft: 12, paddingRight: 5, paddingVertical: 4 },
  editInput: { flexGrow: 1, minWidth: 120, maxWidth: 210, color: colors.textPrimary, fontSize: 16, lineHeight: 22, fontWeight: '600', paddingVertical: 7, paddingRight: 4 },
  iconButton: { width: 30, height: 32, alignItems: 'center', justifyContent: 'center' },
  addRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  addInput: { flex: 1, minWidth: 0, minHeight: 42, borderRadius: radius.round, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.white, paddingHorizontal: 16, paddingVertical: 8, color: colors.textPrimary, fontSize: 16 },
  addButton: { minHeight: 42, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, borderRadius: radius.round, backgroundColor: colors.brand, paddingHorizontal: 14 },
  addButtonText: { color: colors.white, fontSize: 15, fontWeight: '700' },
  muted: { opacity: 0.5 },
  disabled: { opacity: 0.3 },
});
