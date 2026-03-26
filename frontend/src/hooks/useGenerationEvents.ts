import { useEffect, useRef } from 'react';

const BASE = import.meta.env.VITE_API_URL ?? '';

export interface ArtworkReadyEvent {
  artwork_id: string;
  voter_count: number;
  voter_ids: string[];
  svg_content: string;
  trace_text: string;
}

export interface ThinkingPassageEvent {
  node_id: string;
  source_title: string;
  author: string;
  passage: string;
  weight: number;
}

export interface ParameterDecidedEvent {
  parameter: string;
  value: string;
  reason: string;
}

export interface GenerationReasoningEvent {
  step: string;
  description: string;
}

export interface GenerationEventHandlers {
  onGenerationStarted?: () => void;
  onArtworkReady?: (event: ArtworkReadyEvent) => void;
  onThinkingPassage?: (event: ThinkingPassageEvent) => void;
  onParameterDecided?: (event: ParameterDecidedEvent) => void;
  onGenerationReasoning?: (event: GenerationReasoningEvent) => void;
}

/**
 * Subscribe to generation SSE events from /stream.
 *
 * Handles both the generation lifecycle events (started, ready) and the
 * B2.2 consciousness terminal events (thinking_passage, parameter_decided,
 * generation_reasoning) that stream the robot's internal reasoning in real time.
 */
export function useGenerationEvents(handlers: GenerationEventHandlers): void {
  // Keep stable refs so the effect doesn't re-subscribe on every render
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    const es = new EventSource(`${BASE}/stream`);

    es.onerror = (err) => console.error('[SSE] error', err);

    es.onmessage = (e) => {
      let payload: Record<string, unknown>;
      try {
        payload = JSON.parse(e.data);
      } catch {
        return;
      }

      const type = payload.type as string;

      if (type === 'generation_started') {
        handlersRef.current.onGenerationStarted?.();
      } else if (type === 'artwork_ready') {
        handlersRef.current.onArtworkReady?.({
          artwork_id: payload.artwork_id as string,
          voter_count: payload.voter_count as number,
          voter_ids: (payload.voter_ids as string[]) ?? [],
          svg_content: (payload.svg_content as string) ?? '',
          trace_text: (payload.trace_text as string) ?? '',
        });
      } else if (type === 'thinking_passage') {
        handlersRef.current.onThinkingPassage?.({
          node_id: payload.node_id as string,
          source_title: payload.source_title as string,
          author: payload.author as string,
          passage: payload.passage as string,
          weight: payload.weight as number,
        });
      } else if (type === 'parameter_decided') {
        handlersRef.current.onParameterDecided?.({
          parameter: payload.parameter as string,
          value: payload.value as string,
          reason: payload.reason as string,
        });
      } else if (type === 'generation_reasoning') {
        handlersRef.current.onGenerationReasoning?.({
          step: payload.step as string,
          description: payload.description as string,
        });
      }
    };

    return () => es.close();
  }, []); // connect once, never re-subscribe
}
