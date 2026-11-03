import type { Product } from '../types';

export function contentLineLimit(isMobile: boolean, desktopLines: number): number | undefined {
  return isMobile ? undefined : desktopLines;
}

export function productTitle(product: Pick<Product, 'brand' | 'name'>) {
  const name = (product.name || '').trim();
  const brand = (product.brand || '').trim();
  if (!brand) return name || 'Untitled product';
  if (!name) return brand;
  return name.toLowerCase().includes(brand.toLowerCase()) ? name : `${brand} ${name}`;
}

export function displayTitle(product: Pick<Product, 'id' | 'brand' | 'name'>) {
  if (product.id === 'B07GVWH35S') return 'KabelDirekt 8K HDMI Cable · 15ft';
  if (product.id === 'B0BGNG1294') return 'Amazon Basics HDMI Cable · 10ft';
  if (product.id === 'B0199HAOAU') return 'Amazon Basics HDMI to DVI · 3ft';
  if (product.id === 'B0B59QBY9G') return 'Creative Pebble V2';
  if (product.id === 'B01LXDZ8WB') return 'Edifier R980T';
  if (product.id === 'B08XPWDSWW') return 'TOZO T10 Wireless Earbuds';
  const full = productTitle(product);
  const cut = full.split(/[–—,(]| with | for /i)[0].trim();
  return cut.length > 8 ? cut : full;
}

export function displaySpec(product: Pick<Product, 'id' | 'name'> & { sourceFields?: { features?: string[] } }) {
  if (product.id === 'B07GVWH35S') return '4K@120Hz · 8K@60Hz';
  if (product.id === 'B0BGNG1294') return '4K@60Hz · 18Gbps';
  if (product.id === 'B0199HAOAU') return 'HDMI → DVI · 1080p';
  const feature = (product.sourceFields?.features || [])[0];
  if (!feature) return '';
  return feature.length > 72 ? `${feature.slice(0, 69)}…` : feature;
}

export function formatPrice(product: Pick<Product, 'currency' | 'currentPrice'>) {
  const amount = Number(product.currentPrice);
  if (product.currency === 'USD') return `$${amount.toFixed(2)}`;
  if (product.currency === 'CNY') return `¥${amount}`;
  return `${product.currency} ${amount}`;
}

export function displayPrice(product: Product) {
  if (product.sourceFields && product.sourceFields.price == null) return 'Price unavailable';
  return formatPrice(product);
}

export function formatPriceDelta(product: Pick<Product, 'currency'>, amount: number) {
  if (product.currency === 'USD') return `$${amount.toFixed(2)}`;
  if (product.currency === 'CNY') return `¥${amount}`;
  return `${product.currency} ${amount}`;
}
