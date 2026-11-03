import { Ionicons } from '@expo/vector-icons';
import { Tabs } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useResponsiveLayout } from '../../components/responsive';
import { colors } from '../../theme';

export default function TabsLayout() {
  const layout = useResponsiveLayout();
  const insets = useSafeAreaInsets();
  const bottomInset = layout.isDesktop ? 0 : insets.bottom;
  const tabBody = 66;
  return (
    <Tabs
      initialRouteName="explore"
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.brand,
        tabBarInactiveTintColor: colors.textSoft,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          height: layout.isDesktop ? 0 : tabBody + bottomInset,
          paddingTop: 6,
          paddingBottom: bottomInset,
          width: '100%',
          alignSelf: 'stretch',
          borderTopLeftRadius: 0,
          borderTopRightRadius: 0,
          display: layout.isDesktop ? 'none' : 'flex',
          position: 'relative',
        },
        tabBarItemStyle: {
          paddingTop: 0,
          paddingBottom: 0,
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '700',
          lineHeight: 14,
          marginTop: 2,
        },
      }}
    >
      <Tabs.Screen name="explore" options={{ title: 'Explore', tabBarIcon: ({ color }) => <Ionicons name="storefront-outline" color={color} size={22} /> }} />
      <Tabs.Screen name="index" options={{ title: 'Picki', tabBarIcon: ({ color }) => <Ionicons name="sparkles" color={color} size={22} /> }} />
      <Tabs.Screen name="saved" options={{ title: 'My Picks', tabBarIcon: ({ color }) => <Ionicons name="bookmark-outline" color={color} size={22} /> }} />
    </Tabs>
  );
}
