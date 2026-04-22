"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { buildSupportWebSocketUrl } from "@/features/support/lib/support-websocket";
import type { SupportRealtimeEvent } from "@/features/support/types";

type ConnectionState = "idle" | "connecting" | "open" | "reconnecting" | "closed" | "error";

export function useSupportSocket({
  token,
  path,
  enabled,
  onEvent,
}: {
  token: string | null;
  path: string | null;
  enabled: boolean;
  onEvent: (event: SupportRealtimeEvent) => void;
}) {
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const heartbeatTimerRef = useRef<number | null>(null);
  const attemptsRef = useRef(0);
  const onEventRef = useRef(onEvent);
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");

  onEventRef.current = onEvent;

  const url = useMemo(() => {
    if (!token || !path || !enabled) {
      return null;
    }
    return buildSupportWebSocketUrl(path, token);
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
      if (heartbeatTimerRef.current !== null) {
        window.clearInterval(heartbeatTimerRef.current);
        heartbeatTimerRef.current = null;
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

    function startHeartbeat() {
      heartbeatTimerRef.current = window.setInterval(() => {
        const socket = socketRef.current;
        if (!socket || socket.readyState !== WebSocket.OPEN) {
          return;
        }
        socket.send(JSON.stringify({ type: "support.presence.heartbeat" }));
      }, 15000);
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
        socket.send(JSON.stringify({ type: "support.presence.heartbeat" }));
        startHeartbeat();
      };

      socket.onmessage = (event) => {
        try {
          onEventRef.current(JSON.parse(event.data) as SupportRealtimeEvent);
        } catch {
          // Ignore malformed frames and let REST refetch recover state if needed.
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

  function send(event: Record<string, unknown>) {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return false;
    }
    socket.send(JSON.stringify(event));
    return true;
  }

  return {
    connectionState,
    isConnected: connectionState === "open",
    send,
  };
}
