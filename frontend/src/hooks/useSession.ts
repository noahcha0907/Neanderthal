import { useCallback, useEffect, useRef, useState } from 'react';
import { startSession, endSession, setSessionParams, triggerGenerate, submitConsent, uploadFile } from '../api/client';

// How often the robot generates when a session is active (ms)
const GENERATION_INTERVAL_MS = 8000;

export interface SessionState {
  sessionId: string | null;
  isActive: boolean;
  artworkCount: number;
  parameterCount: number | null; // null = Random
  hadUploads: boolean;
}

export interface SessionControls {
  state: SessionState;
  play: () => Promise<void>;
  stop: () => Promise<void>;
  setParamCount: (n: number | null) => Promise<void>;
  upload: (file: File) => Promise<void>;
  // Called from the consent modal after the user decides
  submitConsent: (artworkConsent: boolean, documentConsent: boolean) => Promise<void>;
  // True while waiting for the user's consent decision after stop
  awaitingConsent: boolean;
  error: string | null;
}

export function useSession(): SessionControls {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isActive, setIsActive] = useState(false);
  const [artworkCount, setArtworkCount] = useState(0);
  const [parameterCount, setParameterCount] = useState<number | null>(null);
  const [hadUploads, setHadUploads] = useState(false);
  const [awaitingConsent, setAwaitingConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Keep a stable ref to sessionId so the interval closure always sees the current value
  const sessionIdRef = useRef<string | null>(null);
  sessionIdRef.current = sessionId;
  // Files queued before a session starts — uploaded immediately after play()
  const pendingUploadsRef = useRef<File[]>([]);

  const artworkCountRef = useRef(0);
  artworkCountRef.current = artworkCount;

  const clearGenInterval = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const startGenInterval = useCallback(() => {
    clearGenInterval();
    // Fire once immediately, then on the regular interval
    const tick = async () => {
      const sid = sessionIdRef.current;
      if (!sid) return;
      try {
        await triggerGenerate(sid);
        setArtworkCount(n => n + 1);
      } catch {
        // Generation failures are non-fatal — keep the session alive
      }
    };
    tick();
    intervalRef.current = setInterval(tick, GENERATION_INTERVAL_MS);
  }, [clearGenInterval]);

  // Clean up on unmount
  useEffect(() => () => clearGenInterval(), [clearGenInterval]);

  const play = useCallback(async () => {
    setError(null);
    try {
      const { session_id } = await startSession();
      setSessionId(session_id);
      setIsActive(true);
      setArtworkCount(0);
      setHadUploads(false);
      // Drain any files queued before the session started
      const queued = pendingUploadsRef.current.splice(0);
      if (queued.length > 0) {
        await Promise.all(queued.map(f => uploadFile(session_id, f)));
        setHadUploads(true);
      }
      startGenInterval();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start session');
    }
  }, [startGenInterval]);

  const stop = useCallback(async () => {
    clearGenInterval();
    setIsActive(false);
    const sid = sessionIdRef.current;
    if (!sid) return;
    try {
      const summary = await endSession(sid);
      setHadUploads(summary.had_uploads);
      setArtworkCount(summary.artwork_count);
      setAwaitingConsent(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to end session');
    }
  }, [clearGenInterval]);

  const handleConsent = useCallback(async (artworkConsent: boolean, documentConsent: boolean) => {
    const sid = sessionIdRef.current;
    if (!sid) return;
    try {
      await submitConsent(sid, artworkConsent, documentConsent);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Consent submission failed');
    } finally {
      setSessionId(null);
      setAwaitingConsent(false);
      setArtworkCount(0);
    }
  }, []);

  const upload = useCallback(async (file: File) => {
    const sid = sessionIdRef.current;
    if (!sid) {
      // Queue for upload when the next session starts
      pendingUploadsRef.current.push(file);
      return;
    }
    await uploadFile(sid, file);
    setHadUploads(true);
  }, []);

  const setParamCount = useCallback(async (n: number | null) => {
    setParameterCount(n);
    const sid = sessionIdRef.current;
    if (!sid) return; // no active session yet — value will be applied on next play
    try {
      await setSessionParams(sid, n);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update parameter count');
    }
  }, []);

  return {
    state: { sessionId, isActive, artworkCount, parameterCount, hadUploads },
    play,
    stop,
    setParamCount,
    upload,
    submitConsent: handleConsent,
    awaitingConsent,
    error,
  };
}
