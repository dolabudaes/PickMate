import { Ionicons } from '@expo/vector-icons';
import { useEffect, useState, type ReactNode } from 'react';
import { Platform, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaFrameContext, SafeAreaInsetsContext } from 'react-native-safe-area-context';
import { colors, radius } from '../theme';
import { LayoutSizeProvider } from './responsive';

export type PreviewMode = 'mobile' | 'desktop';

const SCREEN_W = 393;
const SCREEN_H = 852;
const BEZEL = 12;
const DEVICE_W = SCREEN_W + BEZEL * 2;
const DEVICE_H = SCREEN_H + BEZEL * 2;
const IPHONE_INSETS = { top: 54, right: 0, bottom: 34, left: 0 };
const PREVIEW_KEY = 'pickmate_preview_mode';

function isNarrowWeb() {
  if (Platform.OS !== 'web' || typeof window === 'undefined') return true;
  return window.innerWidth < 768;
}

function readPreview(): PreviewMode {
  if (Platform.OS !== 'web' || typeof sessionStorage === 'undefined') return 'mobile';
  try {
    return sessionStorage.getItem(PREVIEW_KEY) === 'desktop' ? 'desktop' : 'mobile';
  } catch {
    return 'mobile';
  }
}

export function LayoutPreviewProvider({ children }: { children: ReactNode }) {
  const window = useWindowDimensions();
  const [preview, setPreview] = useState<PreviewMode>(readPreview);
  const showSwitch = Platform.OS === 'web' && !isNarrowWeb();
  const usePhoneFrame = showSwitch && preview === 'mobile';

  useEffect(() => {
    if (Platform.OS === 'web' && typeof sessionStorage !== 'undefined') {
      try {
        sessionStorage.setItem(PREVIEW_KEY, preview);
      } catch {
        // Preview selection is optional when browser storage is blocked.
      }
    }
  }, [preview]);

  const switcher = showSwitch ? (
    <PreviewSwitch preview={preview} onChange={setPreview} dock={usePhoneFrame ? 'left' : 'bottomLeft'} />
  ) : null;

  if (!usePhoneFrame) {
    return (
      <View style={styles.root}>
        {children}
        {switcher}
      </View>
    );
  }

  const availW = Math.max(280, window.width - 112);
  const availH = Math.max(480, window.height - 32);
  const scale = Math.min(1, availW / DEVICE_W, availH / DEVICE_H);

  return (
    <View style={styles.root}>
      <View style={styles.stage}>
        <View style={{ width: DEVICE_W * scale, height: DEVICE_H * scale }}>
          <View
            style={[
              styles.device,
              {
                width: DEVICE_W,
                height: DEVICE_H,
                transform: [{ scale }],
                ...(Platform.OS === 'web' ? { transformOrigin: '0 0' } : null),
              },
            ]}
          >
            <View style={styles.screen}>
              <View pointerEvents="none" style={styles.island} />
              <SafeAreaInsetsContext.Provider value={IPHONE_INSETS}>
                <SafeAreaFrameContext.Provider value={{ x: 0, y: 0, width: SCREEN_W, height: SCREEN_H }}>
                  <LayoutSizeProvider width={SCREEN_W} height={SCREEN_H}>
                    {children}
                  </LayoutSizeProvider>
                </SafeAreaFrameContext.Provider>
              </SafeAreaInsetsContext.Provider>
              <View pointerEvents="none" style={styles.homeIndicator} />
            </View>
          </View>
        </View>
      </View>
      {switcher}
    </View>
  );
}

function PreviewSwitch({
  preview,
  onChange,
  dock,
}: {
  preview: PreviewMode;
  onChange: (mode: PreviewMode) => void;
  dock: 'left' | 'bottomLeft';
}) {
  const items: Array<{ id: PreviewMode; label: string; icon: keyof typeof Ionicons.glyphMap }> = [
    { id: 'mobile', label: 'Phone', icon: 'phone-portrait-outline' },
    { id: 'desktop', label: 'Desktop', icon: 'desktop-outline' },
  ];
  return (
    <View style={[styles.switch, dock === 'left' ? styles.switchLeft : styles.switchBottomLeft]}>
      {items.map((item) => {
        const active = preview === item.id;
        return (
          <Pressable
            key={item.id}
            accessibilityRole="button"
            accessibilityLabel={`Show ${item.label} layout`}
            onPress={() => onChange(item.id)}
            style={[styles.switchItem, active && styles.switchActive]}
          >
            <Ionicons name={item.icon} size={18} color={active ? colors.white : colors.textSecondary} />
            <Text style={[styles.switchText, active && styles.switchTextActive]}>{item.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    minHeight: 0,
    overflow: 'hidden',
  },
  stage: {
    flex: 1,
    minHeight: 0,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#DDE1E8',
    paddingLeft: 88,
    paddingRight: 24,
    paddingVertical: 16,
  },
  device: {
    borderRadius: 46,
    backgroundColor: '#0C0D12',
    padding: BEZEL,
    shadowColor: '#000',
    shadowOpacity: 0.28,
    shadowRadius: 28,
    shadowOffset: { width: 0, height: 18 },
  },
  screen: {
    width: SCREEN_W,
    height: SCREEN_H,
    overflow: 'hidden',
    borderRadius: 34,
    backgroundColor: colors.background,
  },
  island: {
    position: 'absolute',
    top: 11,
    alignSelf: 'center',
    left: (SCREEN_W - 126) / 2,
    width: 126,
    height: 34,
    zIndex: 30,
    borderRadius: 20,
    backgroundColor: '#050505',
  },
  homeIndicator: {
    position: 'absolute',
    alignSelf: 'center',
    left: (SCREEN_W - 128) / 2,
    bottom: 7,
    width: 128,
    height: 5,
    zIndex: 30,
    borderRadius: 3,
    backgroundColor: 'rgba(0,0,0,0.28)',
  },
  switch: {
    position: 'absolute',
    zIndex: 50,
    gap: 6,
    borderRadius: 18,
    backgroundColor: colors.surface,
    padding: 6,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    shadowColor: '#000',
    shadowOpacity: 0.12,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
  },
  switchLeft: {
    left: 16,
    top: '50%',
    transform: [{ translateY: -60 }],
  },
  switchBottomLeft: {
    left: 16,
    bottom: 16,
    flexDirection: 'row',
  },
  switchItem: {
    minWidth: 64,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 2,
    borderRadius: 12,
    paddingVertical: 8,
    paddingHorizontal: 10,
  },
  switchActive: {
    backgroundColor: colors.brand,
  },
  switchText: {
    color: colors.textSecondary,
    fontSize: 10,
    fontWeight: '800',
  },
  switchTextActive: {
    color: colors.white,
  },
});
