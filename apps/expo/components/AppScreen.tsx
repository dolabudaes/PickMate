import { Ionicons } from '@expo/vector-icons';
import { Link, usePathname } from 'expo-router';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { usePickMate } from '../store/PickMateStore';
import { colors, radius, spacing } from '../theme';
import { CartNotice } from './CartNotice';
import { ResponsiveContainer } from './ResponsiveContainer';
import { useResponsiveLayout } from './responsive';
import { mobileUtilityActions, primaryNavigationItems } from '../lib/navigation';

export function AppScreen({ children, padded = true }: { children: React.ReactNode; padded?: boolean }) {
  const layout = useResponsiveLayout();
  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={styles.safe}>
      {layout.isDesktop && <DesktopNavigation />}
      {!layout.isDesktop && <MobileUtilityNavigation />}
      <View style={StyleSheet.flatten([styles.shell, padded && { paddingHorizontal: layout.horizontalPadding }])}>{children}</View>
      <CartNotice />
    </SafeAreaView>
  );
}

function MobileUtilityNavigation() {
  const { cart } = usePickMate();
  const actions = mobileUtilityActions(cart.length);
  return (
    <View accessibilityLabel="PickMate mobile navigation" style={styles.mobileHeader}>
      <Link href="/explore" asChild>
        <Pressable accessibilityLabel="Open PickMate Explore" style={styles.mobileLogo}>
          <View style={styles.mobileLogoMark}><Ionicons name="sparkles" size={15} color={colors.white} /></View>
          <Text style={styles.mobileLogoText}>PickMate</Text>
        </Pressable>
      </Link>
      <View style={styles.mobileActions}>
        {actions.map((action) => (
          <Link key={action.id} href={action.href as any} asChild>
            <Pressable accessibilityLabel={action.accessibilityLabel} style={styles.mobileAction}>
              <Ionicons name={action.id === 'search' ? 'search-outline' : 'bag-outline'} size={21} color={colors.textPrimary} />
              {action.id === 'cart' && cart.length ? <View style={styles.mobileBadge}><Text style={styles.mobileBadgeText}>{cart.length}</Text></View> : null}
            </Pressable>
          </Link>
        ))}
      </View>
    </View>
  );
}

function DesktopNavigation() {
  const pathname = usePathname();
  const { cart } = usePickMate();
  const items = primaryNavigationItems;

  return (
    <View style={styles.headerWrap}>
      <ResponsiveContainer>
        <View style={styles.header}>
          <Link href="/explore" asChild>
            <Pressable style={styles.logo}>
              <View style={styles.logoMark}><Ionicons name="sparkles" size={18} color={colors.white} /></View>
              <Text style={styles.logoText}>PickMate</Text>
            </Pressable>
          </Link>
          <View style={styles.nav}>
            {items.map((item) => {
              const active = item.href === '/'
                ? pathname === '/'
                : item.href === '/explore'
                  ? pathname.startsWith('/explore') || pathname.startsWith('/product')
                  : pathname.startsWith(item.href);
              return (
                <Link key={item.href} href={item.href as any} asChild>
                  <Pressable style={StyleSheet.flatten([styles.navItem, active && styles.navItemActive])}>
                    <Text style={StyleSheet.flatten([styles.navText, active && styles.navTextActive])}>{item.label}</Text>
                  </Pressable>
                </Link>
              );
            })}
          </View>
          <View style={styles.headerActions}>
            <Link href="/explore" asChild>
              <Pressable style={styles.desktopSearch}>
                <Ionicons name="search-outline" size={17} color={colors.textSecondary} />
                <Text style={styles.desktopSearchText}>Search products</Text>
              </Pressable>
            </Link>
            <Link href="/saved" asChild>
              <Pressable style={styles.profileButton}>
                <Ionicons name="bag-outline" size={22} color={colors.textPrimary} />
                <View style={styles.cartBadge}><Text style={styles.cartBadgeText}>{cart.length}</Text></View>
              </Pressable>
            </Link>
          </View>
        </View>
      </ResponsiveContainer>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    minHeight: 0,
    backgroundColor: colors.background,
  },
  shell: {
    flex: 1,
    minHeight: 0,
    width: '100%',
    alignSelf: 'center',
    backgroundColor: colors.background,
  },
  mobileHeader: {
    minHeight: 54,
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    backgroundColor: colors.surface,
    paddingHorizontal: 14,
    ...(Platform.OS === 'web'
      ? {
          position: 'sticky' as any,
          top: 0,
          zIndex: 30,
        }
      : null),
  },
  mobileLogo: { minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: 8 },
  mobileLogoMark: { width: 30, height: 30, alignItems: 'center', justifyContent: 'center', borderRadius: 9, backgroundColor: colors.brand },
  mobileLogoText: { color: colors.textPrimary, fontSize: 19, fontWeight: '800', letterSpacing: -0.7 },
  mobileActions: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  mobileAction: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center', borderRadius: radius.round },
  mobileBadge: { position: 'absolute', top: 4, right: 2, minWidth: 16, height: 16, borderRadius: 8, backgroundColor: colors.brand, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 3 },
  mobileBadgeText: { color: colors.white, fontSize: 9, fontWeight: '800' },
  headerWrap: {
    width: '100%',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    backgroundColor: colors.surface,
    ...(Platform.OS === 'web'
      ? {
          position: 'sticky' as any,
          top: 0,
          zIndex: 20,
          backdropFilter: 'blur(10px)',
        }
      : null),
  },
  header: {
    width: '100%',
    minHeight: 72,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.xl,
  },
  logo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  logoMark: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    backgroundColor: colors.brand,
  },
  logoText: {
    color: colors.textPrimary,
    fontSize: 23,
    fontWeight: '700',
    letterSpacing: -1.1,
  },
  nav: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
  },
  navItem: {
    minHeight: 72,
    justifyContent: 'center',
    paddingHorizontal: 20,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  navItemActive: {
    borderBottomColor: colors.brand,
  },
  navText: {
    color: colors.textSecondary,
    fontSize: 13,
    fontWeight: '600',
  },
  navTextActive: {
    color: colors.textPrimary,
  },
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  desktopSearch: {
    minWidth: 230,
    height: 40,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 14,
  },
  desktopSearchText: {
    color: colors.textSoft,
    fontSize: 12,
    fontWeight: '700',
  },
  searchButton: {
    width: 46,
    height: 46,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.round,
    backgroundColor: colors.surface,
  },
  pickiNav: {
    height: 46,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    borderRadius: radius.round,
    backgroundColor: colors.brandSoft,
    paddingHorizontal: spacing.lg,
  },
  pickiNavText: {
    color: colors.brandInk,
    fontWeight: '900',
  },
  profileButton: {
    width: 46,
    height: 46,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.round,
    backgroundColor: colors.surface,
  },
  cartBadge: { position: 'absolute', top: 4, right: 2, minWidth: 16, height: 16, borderRadius: 8, backgroundColor: colors.brand, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 3 },
  cartBadgeText: { color: colors.white, fontSize: 9, fontWeight: '800' },
});
