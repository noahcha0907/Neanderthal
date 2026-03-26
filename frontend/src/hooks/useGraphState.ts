import { useEffect, useState } from 'react';
import { fetchGraphState } from '../api/client';
import type { GraphState } from '../types/graph';

const BASE = import.meta.env.VITE_API_URL ?? '';

export function useGraphState() {
  const [data, setData] = useState<GraphState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchGraphState()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // SSE: listen for graph_updated events. The backend sends unnamed data events
  // (data: {...}) so we use onmessage and filter by type field.
  useEffect(() => {
    const es = new EventSource(`${BASE}/stream`);
    es.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        if (payload.type === 'graph_updated') {
          fetchGraphState().then(setData).catch(console.error);
        }
      } catch {
        // ignore non-JSON keep-alive pings
      }
    };
    return () => es.close();
  }, []);

  return { data, loading, error };
}
