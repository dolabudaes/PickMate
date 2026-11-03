import { Animated, StyleSheet, View } from 'react-native';
import { colors, radius, shadow } from '../theme';

export function PickiAvatar({ tiny = false }: { tiny?: boolean }) {
  return (
    <Animated.View style={StyleSheet.flatten([styles.root, tiny && styles.tiny, shadow])}>
      <View style={StyleSheet.flatten([styles.spark, tiny && styles.tinySpark])} />
      <View style={StyleSheet.flatten([styles.eye, styles.leftEye, tiny && styles.tinyEye])} />
      <View style={StyleSheet.flatten([styles.eye, styles.rightEye, tiny && styles.tinyEye])} />
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  root: {
    width: 54,
    height: 58,
    borderRadius: 22,
    backgroundColor: colors.brand,
    borderWidth: 2,
    borderColor: '#fff8f0',
  },
  tiny: {
    width: 28,
    height: 30,
    borderRadius: 12,
  },
  spark: {
    position: 'absolute',
    top: -7,
    left: 20,
    width: 12,
    height: 12,
    borderRadius: 4,
    backgroundColor: colors.brandInk,
    transform: [{ rotate: '45deg' }],
  },
  tinySpark: {
    top: -4,
    left: 10,
    width: 7,
    height: 7,
    borderRadius: 2,
  },
  eye: {
    position: 'absolute',
    top: 23,
    width: 5,
    height: 5,
    borderRadius: radius.round,
    backgroundColor: colors.textPrimary,
  },
  tinyEye: {
    top: 12,
    width: 3,
    height: 3,
  },
  leftEye: {
    left: 18,
  },
  rightEye: {
    right: 18,
  },
});
