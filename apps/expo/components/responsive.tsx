import { createContext, useContext, useMemo, type ReactNode } from 'react';
import { Platform, useWindowDimensions, View } from 'react-native';
import { responsiveLayoutForSize } from '../lib/navigation';

export type LayoutMode = 'mobile' | 'tablet' | 'desktop' | 'wideDesktop';

type LayoutSize = { width: number; height: number };

const LayoutSizeContext = createContext<LayoutSize | null>(null);

export function LayoutSizeProvider({ width, height, children }: LayoutSize & { children: ReactNode }) {
  return (
    <LayoutSizeContext.Provider value={{ width, height }}>
      <View style={{ flex: 1, width, height, minHeight: 0, overflow: 'hidden' }}>{children}</View>
    </LayoutSizeContext.Provider>
  );
}

export function useLayoutSize() {
  const override = useContext(LayoutSizeContext);
  const window = useWindowDimensions();
  return override ?? window;
}

export function useResponsiveLayout() {
  const { width, height } = useLayoutSize();

  return useMemo(() => {
    const layout = responsiveLayoutForSize(width, height);
    return { ...layout, mode: layout.mode as LayoutMode, isWebDesktop: Platform.OS === 'web' && layout.isDesktop };
  }, [height, width]);
}
