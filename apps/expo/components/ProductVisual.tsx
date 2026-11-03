import { Image } from 'expo-image';
import { useEffect, useMemo, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { productDisplayImages } from '../lib/images';
import type { Product } from '../types';
import { colors, radius } from '../theme';

export function ProductVisual({ product, compact = false, size }: { product: Product; compact?: boolean; size?: number }) {
  const urls = useMemo(() => productDisplayImages(product), [product]);
  const [index, setIndex] = useState(0);
  const current = urls[index];
  const sized = size ? { width: size, height: size, minWidth: size, minHeight: size } : null;

  useEffect(() => {
    setIndex(0);
  }, [product.id, urls.join('|')]);

  if (current) {
    return (
      <View style={StyleSheet.flatten([styles.root, compact && styles.compact, sized])}>
        <Image
          source={{ uri: current }}
          style={styles.image}
          contentFit="contain"
          transition={160}
          onError={() => setIndex((value) => value + 1)}
        />
      </View>
    );
  }

  return <CatalogProductArt product={product} compact={compact} size={size} />;
}

function CatalogProductArt({ product, compact, size }: { product: Product; compact: boolean; size?: number }) {
  const accent = accentFor(product.id || product.brand);
  const sized = size ? { width: size, height: size, minWidth: size, minHeight: size } : null;
  return (
    <View style={StyleSheet.flatten([styles.root, compact && styles.compact, sized, styles.art])}>
      <View style={[styles.case, compact && styles.caseCompact, { backgroundColor: '#161616' }]}>
        <View style={[styles.bud, compact && styles.budCompact, { backgroundColor: accent }]} />
        <View style={[styles.bud, compact && styles.budCompact, { backgroundColor: accent }]} />
      </View>
      {!compact ? <Text style={styles.placeholderText} numberOfLines={1}>{product.brand || 'PickMate'}</Text> : null}
    </View>
  );
}

function accentFor(value: string) {
  const palette = ['#FF6A3D', '#FF6900', '#2EC48A', '#EB0028', '#F5C518', '#4A90D9', '#3D7EFF', '#C41E3A'];
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) hash = (hash + value.charCodeAt(index) * (index + 3)) % palette.length;
  return palette[hash];
}

const styles = StyleSheet.create({
  root: {
    width: '100%',
    height: '100%',
    overflow: 'hidden',
    backgroundColor: '#FAFBFC',
    borderRadius: radius.lg,
  },
  compact: {
    width: 72,
    height: 72,
    minHeight: 72,
    minWidth: 72,
    flexShrink: 0,
    borderRadius: radius.md,
  },
  image: {
    width: '100%',
    height: '100%',
  },
  placeholder: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: colors.surfaceMuted,
  },
  art: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#F4EEE7',
  },
  case: {
    width: 86,
    height: 54,
    borderRadius: 27,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
  },
  caseCompact: {
    width: 46,
    height: 28,
    borderRadius: 14,
    gap: 5,
  },
  bud: {
    width: 18,
    height: 18,
    borderRadius: 9,
  },
  budCompact: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  placeholderText: {
    color: colors.textSoft,
    fontSize: 12,
    fontWeight: '800',
  },
});
