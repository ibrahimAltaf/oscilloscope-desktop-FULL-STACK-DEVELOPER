import { useEffect, useRef, useCallback } from "react";
import type { SignalBatch } from "@/types/signal";
import { isSignalBatch } from "@/types/signal";

export type WsState = "idle" | "connecting" | "open" | "closed" | "error";

export type UseSignalWebSocketOptions = {
  url: string | null;
  enabled: boolean;
  /** Batched: all messages received in one animation frame (fewer React/callback invocations). */
  onBatches: (batches: SignalBatch[]) => void;
  onConnectionChange?: (s: WsState, detail?: string) => void;
};

/**
 * WebSocket client: parse messages, queue them, flush once per rAF as a batch.
 */
export function useSignalWebSocket({
  url,
  enabled,
  onBatches,
  onConnectionChange,
}: UseSignalWebSocketOptions): void {
  // Guard against missing URL or disabled flag; treat as idle without throwing.
  if (!enabled || !url) {
    onConnectionChange?.("idle");
  }
  const onBatchesRef = useRef(onBatches);
  onBatchesRef.current = onBatches;
  const onConnRef = useRef(onConnectionChange);
  onConnRef.current = onConnectionChange;

  const queueRef = useRef<SignalBatch[]>([]);
  const rafRef = useRef<number | null>(null);

  const flush = useCallback(() => {
    rafRef.current = null;
    const q = queueRef.current;
    if (q.length === 0) return;
    const drain = q.splice(0, q.length);
    onBatchesRef.current(drain);
  }, []);

  const scheduleFlush = useCallback(() => {
    if (rafRef.current != null) return;
    rafRef.current = requestAnimationFrame(flush);
  }, [flush]);

  useEffect(() => {
    if (!enabled || !url) {
      onConnRef.current?.("idle");
      return;
    }

    let ws: WebSocket | null = null;
    let closed = false;

    onConnRef.current?.("connecting");
    try {
      ws = new WebSocket(url);
    } catch (e) {
      onConnRef.current?.("error", e instanceof Error ? e.message : String(e));
      return;
    }

    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
      if (closed) return;
      onConnRef.current?.("open");
    };

    ws.onmessage = (ev) => {
      if (closed) return;
      try {
        const raw =
          typeof ev.data === "string"
            ? ev.data
            : new TextDecoder().decode(ev.data as ArrayBuffer);
        const parsed: unknown = JSON.parse(raw);
        if (isSignalBatch(parsed)) queueRef.current.push(parsed);
      } catch {
        /* ignore malformed */
      }
      scheduleFlush();
    };

    ws.onerror = () => {
      onConnRef.current?.("error", "WebSocket error");
    };

    ws.onclose = () => {
      if (closed) return;
      onConnRef.current?.("closed");
    };

    return () => {
      closed = true;
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      queueRef.current.length = 0;
      ws?.close();
      ws = null;
      onConnRef.current?.("idle");
    };
  }, [enabled, url, scheduleFlush]);
}
