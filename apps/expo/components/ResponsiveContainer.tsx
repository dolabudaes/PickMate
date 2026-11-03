import { StyleSheet, View } from 'react-native';
import { useResponsiveLayout } from './responsive';

export function ResponsiveContainer({ children, maxWidth, fill = false }: { children: React.ReactNode; maxWidth?: number; fill?: boolean }) {
  const layout = useResponsiveLayout();
  return (
    <View
      style={StyleSheet.flatten([
        styles.container,
        fill && styles.fill,
        {
          maxWidth: maxWidth ?? layout.maxWidth,
          paddingHorizontal: layout.horizontalPadding,
        },
      ])}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
    alignSelf: 'center',
  },
  fill: {
    flex: 1,
  },
});
