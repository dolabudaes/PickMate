import 'react-native-gesture-handler';
import { BottomSheetModalProvider } from '@gorhom/bottom-sheet';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { View } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AskPickiHost } from '../components/AskPickiHost';
import { CompareSheet } from '../components/CompareSheet';
import { LayoutPreviewProvider } from '../components/LayoutPreview';
import { PickMateProvider } from '../store/PickMateStore';
import { colors } from '../theme';

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <LayoutPreviewProvider>
          <PickMateProvider>
            <BottomSheetModalProvider>
              <StatusBar style="dark" />
              <View style={{ flex: 1, overflow: 'hidden' }}>
                <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.background } }}>
                  <Stack.Screen name="(tabs)" />
                  <Stack.Screen name="product/[id]" options={{ presentation: 'card' }} />
                  <Stack.Screen name="status" options={{ headerShown: true, title: 'API Status' }} />
                </Stack>
                <AskPickiHost />
                <CompareSheet />
              </View>
            </BottomSheetModalProvider>
          </PickMateProvider>
        </LayoutPreviewProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
