import type { GraphState, GraphNode } from '../types/graph';

const BASE = import.meta.env.VITE_API_URL ?? '';

// top_k controls how many similarity edges per node are returned.
// 5 keeps the payload ~35k edges instead of 1.87M — fast to download and render.
export async function fetchGraphState(topK = 5): Promise<GraphState> {
  const res = await fetch(`${BASE}/graph/state?top_k=${topK}`);
  if (!res.ok) throw new Error(`Graph state fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchNodeDetail(nodeId: string): Promise<GraphNode | null> {
  const res = await fetch(`${BASE}/graph/node/${encodeURIComponent(nodeId)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Node fetch failed: ${res.status}`);
  return res.json();
}

export async function startSession(): Promise<{ session_id: string; started_at: string }> {
  const res = await fetch(`${BASE}/session/start`, { method: 'POST' });
  if (!res.ok) throw new Error(`Session start failed: ${res.status}`);
  return res.json();
}

export async function endSession(sessionId: string): Promise<{ artwork_count: number; had_uploads: boolean }> {
  const res = await fetch(`${BASE}/session/end`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!res.ok) throw new Error(`Session end failed: ${res.status}`);
  return res.json();
}

export async function setSessionParams(
  sessionId: string,
  parameterCount: number | null,
): Promise<void> {
  const res = await fetch(`${BASE}/session/params`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, parameter_count: parameterCount }),
  });
  if (!res.ok) throw new Error(`Session params failed: ${res.status}`);
}

export async function triggerGenerate(sessionId?: string): Promise<{ artwork_id: string }> {
  const res = await fetch(`${BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId ?? null }),
  });
  if (!res.ok) throw new Error(`Generate failed: ${res.status}`);
  return res.json();
}

export async function fetchPortfolio(): Promise<Array<{ artwork_id: string; created_at: string }>> {
  const res = await fetch(`${BASE}/portfolio`);
  if (!res.ok) throw new Error(`Portfolio fetch failed: ${res.status}`);
  return res.json();
}

export async function uploadFile(
  sessionId: string,
  file: File,
): Promise<{ chunks_added: number; session_id: string }> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE}/upload`, {
    method: 'POST',
    headers: { 'X-Session-ID': sessionId },
    body: form,
  });
  if (!res.ok) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const detail = await res.json().catch(() => ({})) as any;
    throw new Error(detail?.detail ?? `Upload failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchPortfolioItem(
  artworkId: string,
): Promise<{ artwork_id: string; svg_content: string; trace_text: string; created_at: string; voter_ids: string[] }> {
  const res = await fetch(`${BASE}/portfolio/${encodeURIComponent(artworkId)}`);
  if (!res.ok) throw new Error(`Portfolio fetch failed: ${res.status}`);
  return res.json();
}

export async function submitConsent(
  sessionId: string,
  artworkConsent: boolean,
  documentConsent: boolean,
): Promise<{ artworks_ingested: number; documents_added: number }> {
  const res = await fetch(`${BASE}/consent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      artwork_consent: artworkConsent,
      document_consent: documentConsent,
    }),
  });
  if (!res.ok) throw new Error(`Consent failed: ${res.status}`);
  return res.json();
}
