"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { buildCommerceWebSocketUrl } from "@/features/commerce/lib/commerce-websocket";
import type { CommerceRealtimeEvent } from "@/features/commerce/types";

type ConnectionState = "idle" | "connecting" | "open" | "reconnecting" | "closed" | "error";

export function useCommerceSocket({
  token,
  path,
  enabled,
  onEvent,
}: {
  token: string | null;
  path: string | null;
  enabled: boolean;
  onEvent: (event: CommerceRealtimeEvent) => void;
}) {
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const attemptsRef = useRef(0);
  const onEventRef = useRef(onEvent);
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");

  onEventRef.current = onEvent;

  const url = useMemo(() => {
    if (!token || !path || !enabled) {
      return null;
    }
    return buildCommerceWebSocketUrl(path, token);
  }, [enabled, path, token]);

  useEffect(() => {
    if (!url) {
      setConnectionState("idle");
      return undefined;
    }

    const socketUrl = url;
    let cancelled = false;

    function clearTimers() {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    }

    function scheduleReconnect() {
      if (cancelled) {
        return;
      }
      attemptsRef.current += 1;
      setConnectionState("reconnecting");
      const delay = Math.min(1000 * 2 ** Math.min(attemptsRef.current, 4), 12000);
      reconnectTimerRef.current = window.setTimeout(connect, delay);
    }

    function connect() {
      clearTimers();
      setConnectionState(attemptsRef.current > 0 ? "reconnecting" : "connecting");
      const socket = new WebSocket(socketUrl);
      socketRef.current = socket;

      socket.onopen = () => {
        if (cancelled) {
          socket.close();
          return;
        }
        attemptsRef.current = 0;
        setConnectionState("open");
      };

      socket.onmessage = (event) => {
        try {
          onEventRef.current(JSON.parse(event.data) as CommerceRealtimeEvent);
        } catch {
          // Ignore malformed frames and let REST fallback recover state.
        }
      };

      socket.onerror = () => {
        setConnectionState("error");
      };

      socket.onclose = (event) => {
        clearTimers();
        if (!cancelled && event.code !== 4401 && event.code !== 4403) {
          scheduleReconnect();
        } else {
          setConnectionState("closed");
        }
      };
    }

    connect();

    return () => {
      cancelled = true;
      clearTimers();
      const socket = socketRef.current;
      socketRef.current = null;
      if (socket && socket.readyState < WebSocket.CLOSING) {
        socket.close();
      }
    };
  }, [url]);

  return {
    connectionState,
    isConnected: connectionState === "open",
  };
}

