import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { AppScreen } from '../../components/AppScreen';
import { ResponsiveContainer } from '../../components/ResponsiveContainer';
import { ShoppingCatalog } from '../../components/ShoppingCatalog';
import { useResponsiveLayout } from '../../components/responsive';
import { colors, spacing } from '../../theme';

export default function ExploreScreen() {
  const layout = useResponsiveLayout();
  return (
    <AppScreen padded={false}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: layout.isDesktop ? 48 : layout.tabBarHeight + 24 }}>
        <ResponsiveContainer maxWidth={1440}>
          <View style={styles.intro}>
            <Text style={[styles.title, layout.isDesktop && styles.titleDesktop]}>Explore</Text>
          </View>
        </ResponsiveContainer>
        <ShoppingCatalog />
      </ScrollView>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  intro: { paddingTop: spacing.xl, paddingHorizontal: spacing.md },
  title: { marginTop: 12, color: colors.textPrimary, fontSize: 36, fontWeight: '700', letterSpacing: -1.6 },
  titleDesktop: { fontSize: 52, letterSpacing: -2.4 },
});
