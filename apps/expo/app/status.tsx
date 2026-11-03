import { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { API_BASE_URL } from '../services/api/client';

type HealthState =
  | { kind: 'loading' }
  | { kind: 'ok'; body: string }
  | { kind: 'error'; message: string };

export default function StatusScreen() {
  const [state, setState] = useState<HealthState>({ kind: 'loading' });

  const ping = useCallback(async () => {
    setState({ kind: 'loading' });
    try {
      const response = await fetch(`${API_BASE_URL}/health`);
      const text = await response.text();
      if (!response.ok) {
        setState({ kind: 'error', message: `HTTP ${response.status}: ${text}` });
        return;
      }
      setState({ kind: 'ok', body: text });
    } catch (error) {
      setState({
        kind: 'error',
        message: error instanceof Error ? error.message : String(error),
      });
    }
  }, []);

  useEffect(() => {
    void ping();
  }, [ping]);

  return (
    <View style={styles.root}>
      <Text style={styles.title}>PickMate API</Text>
      <Text style={styles.meta}>{API_BASE_URL}/health</Text>
      {state.kind === 'loading' ? <Text style={styles.body}>Checking…</Text> : null}
      {state.kind === 'ok' ? <Text style={styles.ok}>{state.body}</Text> : null}
      {state.kind === 'error' ? <Text style={styles.err}>{state.message}</Text> : null}
      <Pressable onPress={ping} style={styles.button}>
        <Text style={styles.buttonText}>Retry</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    padding: 24,
    justifyContent: 'center',
    gap: 12,
    backgroundColor: '#fff',
  },
  title: {
    fontSize: 22,
    fontWeight: '600',
  },
  meta: {
    fontSize: 14,
    color: '#555',
  },
  body: {
    fontSize: 15,
  },
  ok: {
    fontSize: 14,
    fontFamily: 'monospace',
    color: '#166534',
  },
  err: {
    fontSize: 14,
    color: '#b91c1c',
  },
  button: {
    alignSelf: 'flex-start',
    paddingVertical: 10,
    paddingHorizontal: 16,
    backgroundColor: '#111',
  },
  buttonText: {
    color: '#fff',
    fontSize: 15,
  },
});
