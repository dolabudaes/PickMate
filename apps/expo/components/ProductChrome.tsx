import { Ionicons } from '@expo/vector-icons';
import { type ComponentProps, type ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, radius, shadow, spacing } from '../theme';
import { useResponsiveLayout } from './responsive';

type IconName = ComponentProps<typeof Ionicons>['name'];

export function ProductPageHeader({
  kicker,
  title,
  subtitle,
  accessory,
}: {
  kicker: string;
  title: string;
  subtitle: string;
  accessory?: ReactNode;
}) {
  const layout = useResponsiveLayout();
  return (
    <View style={styles.headerBlock}>
      <View style={[styles.header, layout.isDesktop && styles.headerDesktop, layout.isTablet && styles.headerTablet]}>
        <View style={layout.isDesktop ? styles.headerCopyDesktop : undefined}>
          <Text style={[styles.kicker, layout.isDesktop && styles.kickerDesktop]}>{kicker}</Text>
          <Text style={[styles.title, layout.isDesktop && styles.titleDesktop]}>{title}</Text>
          <Text style={styles.subtitle}>{subtitle}</Text>
        </View>
        {accessory ? <View style={[styles.accessory, layout.isDesktop && styles.accessoryDesktop]}>{accessory}</View> : null}
      </View>
    </View>
  );
}

export function SectionPanel({
  title,
  icon,
  meta,
  children,
  style,
}: {
  title: string;
  icon?: IconName;
  meta?: string;
  children: ReactNode;
  style?: object;
}) {
  return (
    <View style={[styles.panel, shadow, style]}>
      <View style={styles.panelHead}>
        <View style={styles.panelTitleWrap}>
          {icon ? <Ionicons name={icon} size={18} color={colors.brand} /> : null}
          <Text style={styles.panelTitle}>{title}</Text>
        </View>
        {meta ? <Text style={styles.metaTag}>{meta}</Text> : null}
      </View>
      {children}
    </View>
  );
}

export function StatCard({
  icon,
  label,
  value,
}: {
  icon: IconName;
  label: string;
  value: string;
}) {
  return (
    <View style={[styles.statCard, shadow]}>
      <Ionicons name={icon} size={18} color={colors.brand} />
      <View style={styles.statCopy}>
        <Text style={styles.statLabel}>{label}</Text>
        <Text style={styles.statValue} numberOfLines={1}>{value}</Text>
      </View>
    </View>
  );
}

export function Pill({
  label,
  icon,
  active = false,
  tone = 'neutral',
  onPress,
}: {
  label: string;
  icon?: IconName;
  active?: boolean;
  tone?: 'neutral' | 'brand' | 'success' | 'warning';
  onPress?: () => void;
}) {
  const content = (
    <>
      {icon ? <Ionicons name={icon} size={15} color={pillInk(tone, active)} /> : null}
      <Text style={[styles.pillText, { color: pillInk(tone, active) }]} numberOfLines={1}>{label}</Text>
    </>
  );
  const pillStyle = [styles.pill, pillToneStyle(tone), active && styles.pillActive];

  if (onPress) {
    return (
      <Pressable onPress={onPress} style={pillStyle}>
        {content}
      </Pressable>
    );
  }

  return <View style={pillStyle}>{content}</View>;
}

export function ActionButton({
  label,
  icon,
  onPress,
  variant = 'primary',
  disabled = false,
}: {
  label: string;
  icon?: IconName;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'ghost';
  disabled?: boolean;
}) {
  const ink = variant === 'primary' ? colors.white : colors.textPrimary;
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={[styles.action, styles[`${variant}Action`], disabled && styles.actionDisabled]}
    >
      {icon ? <Ionicons name={icon} size={16} color={disabled ? colors.textSoft : ink} /> : null}
      <Text style={[styles.actionText, { color: disabled ? colors.textSoft : ink }]}>{label}</Text>
    </Pressable>
  );
}

export function EmptyState({
  title,
  text,
  icon = 'sparkles-outline',
  actions,
}: {
  title: string;
  text: string;
  icon?: IconName;
  actions?: ReactNode;
}) {
  return (
    <View style={styles.empty}>
      <View style={styles.emptyIcon}>
        <Ionicons name={icon} size={24} color={colors.brand} />
      </View>
      <Text style={styles.emptyTitle}>{title}</Text>
      <Text style={styles.emptyText}>{text}</Text>
      {actions ? <View style={styles.emptyActions}>{actions}</View> : null}
    </View>
  );
}

function pillInk(tone: 'neutral' | 'brand' | 'success' | 'warning', active: boolean) {
  if (active || tone === 'brand') return colors.brandInk;
  if (tone === 'success') return colors.success;
  if (tone === 'warning') return colors.warning;
  return colors.textSecondary;
}

function pillToneStyle(tone: 'neutral' | 'brand' | 'success' | 'warning') {
  if (tone === 'brand') return styles.pillBrand;
  if (tone === 'success') return styles.pillSuccess;
  if (tone === 'warning') return styles.pillWarning;
  return styles.pillNeutral;
}

const styles = StyleSheet.create({
  headerBlock: {
    paddingTop: 24,
  },
  header: {
    gap: spacing.lg,
  },
  headerDesktop: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 36,
  },
  headerTablet: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: spacing.xl,
  },
  headerCopyDesktop: {
    flex: 0.74,
    minWidth: 320,
  },
  kicker: {
    color: colors.brand,
    fontSize: 12,
    fontWeight: '900',
  },
  kickerDesktop: {
    fontSize: 13,
  },
  title: {
    color: colors.textPrimary,
    fontSize: 28,
    fontWeight: '900',
  },
  titleDesktop: {
    fontSize: 31,
    lineHeight: 38,
  },
  subtitle: {
    marginTop: 7,
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
  },
  accessory: {
    minWidth: 0,
  },
  accessoryDesktop: {
    flex: 1.26,
    minWidth: 480,
  },
  panel: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    backgroundColor: colors.surface,
    padding: spacing.xl,
  },
  panelHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  panelTitleWrap: {
    flex: 1,
    minWidth: 0,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  panelTitle: {
    color: colors.textPrimary,
    fontSize: 20,
    fontWeight: '900',
  },
  statCard: {
    flex: 1,
    minHeight: 74,
    minWidth: 0,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    backgroundColor: colors.surface,
    padding: spacing.md,
  },
  statCopy: {
    flex: 1,
    minWidth: 0,
  },
  statLabel: {
    color: colors.textSoft,
    fontSize: 12,
    fontWeight: '900',
  },
  statValue: {
    marginTop: 3,
    color: colors.textPrimary,
    fontSize: 15,
    fontWeight: '900',
  },
  metaTag: {
    overflow: 'hidden',
    borderRadius: radius.round,
    backgroundColor: colors.surfaceWarm,
    color: colors.textSecondary,
    paddingVertical: 6,
    paddingHorizontal: spacing.md,
    fontSize: 12,
    fontWeight: '900',
  },
  pill: {
    minHeight: 34,
    maxWidth: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderRadius: radius.round,
    paddingVertical: 8,
    paddingHorizontal: spacing.md,
  },
  pillNeutral: {
    backgroundColor: colors.surfaceWarm,
  },
  pillBrand: {
    backgroundColor: colors.brandSoft,
  },
  pillSuccess: {
    backgroundColor: colors.successSoft,
  },
  pillWarning: {
    backgroundColor: colors.warningSoft,
  },
  pillActive: {
    backgroundColor: colors.brandSoft,
  },
  pillText: {
    flexShrink: 1,
    fontSize: 12,
    fontWeight: '900',
  },
  action: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    borderRadius: radius.md,
    paddingVertical: 12,
    paddingHorizontal: spacing.lg,
  },
  primaryAction: {
    backgroundColor: colors.brand,
  },
  secondaryAction: {
    backgroundColor: colors.surfaceMuted,
  },
  ghostAction: {
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  actionDisabled: {
    opacity: 0.58,
  },
  actionText: {
    fontSize: 13,
    fontWeight: '900',
  },
  empty: {
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    backgroundColor: colors.surfaceWarm,
    paddingVertical: spacing.xxl,
    paddingHorizontal: spacing.xl,
  },
  emptyIcon: {
    width: 52,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.round,
    backgroundColor: colors.brandSoft,
  },
  emptyTitle: {
    marginTop: spacing.md,
    color: colors.textPrimary,
    fontSize: 22,
    lineHeight: 28,
    fontWeight: '900',
    textAlign: 'center',
  },
  emptyText: {
    marginTop: spacing.sm,
    maxWidth: 440,
    color: colors.textSecondary,
    fontSize: 15,
    lineHeight: 22,
    textAlign: 'center',
  },
  emptyActions: {
    marginTop: spacing.lg,
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: spacing.sm,
  },
});
