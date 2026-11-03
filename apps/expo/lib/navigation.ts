export const primaryNavigationItems = [
  { href: '/explore', label: 'Explore' },
  { href: '/', label: 'Picki' },
  { href: '/saved', label: 'My Picks' },
] as const;

export type ResponsiveLayout = {
  width: number;
  height: number;
  isMobile: boolean;
  isNarrowPhone: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  isWideDesktop: boolean;
  mode: 'mobile' | 'tablet' | 'desktop' | 'wideDesktop';
  contentWidth: number;
  pageWidth: number;
  maxWidth: number | undefined;
  columns: number;
  productGridColumns: number;
  horizontalPadding: number;
  columnGap: number;
  rowGap: number;
  tabBarHeight: number;
  pickiPresentation: 'drawer' | 'bottomSheet';
};

export function responsiveLayoutForSize(width: number, height: number): ResponsiveLayout {
  const isTablet = width >= 768 && width < 1024;
  const isDesktop = width >= 1024;
  const isWideDesktop = width >= 1680;
  const isMobile = width < 768;
  const isNarrowPhone = width <= 430;
  const horizontalPadding = isNarrowPhone ? 14 : isMobile ? 16 : isTablet ? 24 : width >= 1680 ? 32 : 24;
  const maxWidth = width >= 2200 ? 2040 : undefined;
  const pageWidth = isDesktop ? Math.min(width, maxWidth ?? width) : width;
  const contentWidth = Math.max(0, pageWidth - horizontalPadding * 2);
  const columns = isMobile
    ? width < 360 ? 1 : 2
    : isTablet
      ? 3
      : contentWidth >= 1360
        ? 5
        : contentWidth >= 1060
          ? 4
          : 3;
  const columnGap = isMobile ? 8 : isTablet ? 16 : 18;

  return {
    width,
    height,
    isMobile,
    isNarrowPhone,
    isTablet,
    isDesktop,
    isWideDesktop,
    mode: isWideDesktop ? 'wideDesktop' : isDesktop ? 'desktop' : isTablet ? 'tablet' : 'mobile',
    contentWidth,
    pageWidth,
    maxWidth,
    columns,
    productGridColumns: columns,
    horizontalPadding,
    columnGap,
    rowGap: isMobile ? 12 : isTablet ? 18 : 20,
    tabBarHeight: isDesktop ? 0 : 92,
    pickiPresentation: isDesktop ? 'drawer' : 'bottomSheet',
  };
}

export function mobileUtilityActions(cartCount: number) {
  return [
    { id: 'search', href: '/explore', accessibilityLabel: 'Search products' },
    { id: 'cart', href: '/saved', accessibilityLabel: `Open cart with ${cartCount} products` },
  ];
}

export function conversationHistorySurface(
  platform: string,
  isDesktop: boolean,
): 'rail' | 'inline' | 'modal' {
  if (isDesktop) return 'rail';
  return platform === 'web' ? 'inline' : 'modal';
}

export function relatedChatsSurface(isMobile: boolean): 'inline' | 'modal' {
  return isMobile ? 'inline' : 'modal';
}

const DEMO_SELECTED_PRODUCT_IDS = ['B0BGNG1294', 'B0199HAOAU'] as const;

export function demoInitialSelectedProductIds(): string[] {
  return [...DEMO_SELECTED_PRODUCT_IDS];
}
