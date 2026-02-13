import { useEffect, useRef, useCallback, useState } from 'react';
import type { WSEvent } from '../types/api';

interface UseWebSocketOptions {
  sessionId: string | null;
  onEvent?: (event: WSEvent) => void;
}

const MAX_RETRIES = 5;
const BASE_DELAY_MS = 1000;

export function useWebSocket({ sessionId, onEvent }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<WSEvent[]>([]);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;
  const retriesRef = useRef(0);
  const mountedRef = useRef(true);

  const addEvent = useCallback((event: WSEvent) => {
    setEvents(prev => [...prev, event]);
    onEventRef.current?.(event);
  }, []);

  const clearEvents = useCallback(() => setEvents([]), []);

  useEffect(() => {
    mountedRef.current = true;
    if (!sessionId) return;

    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      if (!mountedRef.current) return;

      // Build WS URL relative to current host
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/sessions/${sessionId}`;
      console.log('[WS] Connecting to', wsUrl);

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setConnected(true);
        retriesRef.current = 0;
        console.log('[WS] Connected to', sessionId);
      };

      ws.onmessage = (e) => {
        try {
          const data: WSEvent = JSON.parse(e.data);
          if (data.type === 'event_history') {
            const historyEvent = data as Extract<WSEvent, { type: 'event_history' }>;
            historyEvent.events.forEach(addEvent);
          } else {
            addEvent(data);
          }
        } catch {
          console.warn('[WS] Failed to parse message:', e.data);
        }
      };

      ws.onclose = (e) => {
        if (!mountedRef.current) return;
        setConnected(false);
        console.log('[WS] Disconnected', e.code, e.reason);

        // Reconnect if not a normal close and retries remain
        if (e.code !== 1000 && retriesRef.current < MAX_RETRIES) {
          const delay = BASE_DELAY_MS * Math.pow(2, retriesRef.current);
          retriesRef.current++;
          console.log(`[WS] Reconnecting in ${delay}ms (attempt ${retriesRef.current}/${MAX_RETRIES})`);
          reconnectTimer = setTimeout(connect, delay);
        }
      };

      ws.onerror = (err) => {
        console.error('[WS] Error:', err);
      };
    }

    connect();

    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectTimer);
      if (wsRef.current) {
        wsRef.current.close(1000, 'component unmounted');
        wsRef.current = null;
      }
      setConnected(false);
    };
  }, [sessionId, addEvent]);

  return { connected, events, clearEvents };
}
