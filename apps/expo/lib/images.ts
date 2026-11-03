import { API_BASE_URL } from '../services/api/client';
import type { Product } from '../types';

const AMAZON_SUFFIX = /\._[A-Za-z0-9,_]+\.(jpg|jpeg|png|webp)$/i;

export function productDisplayImages(product: Product) {
  const collected = collectRawUrls(product).flatMap(expandUrl);
  return unique([
    `${API_BASE_URL}/media/product/${encodeURIComponent(product.id)}`,
    ...collected,
    `${API_BASE_URL}/media/catalog/${encodeURIComponent(product.id)}`,
  ]);
}

function collectRawUrls(product: Product) {
  const raw = product.sourceFields?.rawAttributes;
  const nested = raw && typeof raw.data === 'object' && raw.data ? raw.data as Record<string, unknown> : undefined;
  return [
    ...asUrlList(product.imageUrls),
    ...asUrlList(nested?.images),
    ...asUrlList(nested?.image),
    ...asUrlList(nested?.hiRes),
    ...asUrlList(raw?.images),
  ];
}

function expandUrl(url: string) {
  const upgraded = upgradeAmazon(url);
  if (/^https?:\/\//i.test(upgraded)) {
    return [`${API_BASE_URL}/media?url=${encodeURIComponent(upgraded)}`];
  }
  const token = catalogImageToken(upgraded);
  return token ? [`${API_BASE_URL}/media/catalog/${encodeURIComponent(token)}`] : [];
}

function catalogImageToken(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return '';
  if (trimmed.startsWith('mvp://')) {
    return trimmed.replace('mvp://', '').split('/')[0];
  }
  if (/^[\w.-]+$/.test(trimmed)) return trimmed;
  return '';
}

function upgradeAmazon(url: string) {
  const trimmed = url.trim();
  return AMAZON_SUFFIX.test(trimmed) ? trimmed.replace(AMAZON_SUFFIX, '._AC_SL800_.$1') : trimmed;
}

function asUrlList(value: unknown): string[] {
  if (!value) return [];
  if (typeof value === 'string') {
    return [value, ...Array.from(value.matchAll(/https?:\/\/[^\s"']+/g), (match) => match[0])];
  }
  if (Array.isArray(value)) return value.flatMap(asUrlList);
  return [];
}

function unique(items: string[]) {
  return [...new Set(items.filter(Boolean))];
}
