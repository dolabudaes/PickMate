import { Platform } from 'react-native';

export const colors = {
  background: '#FFFFFF',
  surface: '#FFFFFF',
  surfaceWarm: '#FFF3EC',
  surfaceMuted: '#F7F6F4',
  textPrimary: '#262522',
  textSecondary: '#85817C',
  textSoft: '#A29F99',
  brand: '#E95421',
  brandSecondary: '#D64718',
  brandSoft: '#FFF3EC',
  brandInk: '#D64718',
  success: '#29805A',
  successSoft: '#EDF7F0',
  warning: '#C75B12',
  warningSoft: '#FFF2E8',
  border: '#ECEAE6',
  white: '#FFFFFF',
  overlay: 'rgba(23,21,19,0.40)',
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 22,
  xxl: 32,
};

export const radius = {
  sm: 8,
  md: 10,
  lg: 12,
  xl: 16,
  round: 999,
};

export const typography = {
  title: 28,
  section: 20,
  body: 15,
  small: 12,
};

export const shadow = Platform.select({
  web: {
    boxShadow: '0 2px 10px rgba(34, 34, 34, 0.06)',
  },
  default: {
    shadowColor: '#222222',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 6,
    elevation: 1,
  },
});
