"use client";

import { useEffect, useMemo, useState } from "react";

export function useTokenCountdown(expiresAt: string | null | undefined, tickMs = 30_000): number | null {
  const [nowTs, setNowTs] = useState<number | null>(null);

  useEffect(() => {
    setNowTs(Date.now());
    const interval = setInterval(() => {
      setNowTs(Date.now());
    }, tickMs);

    return () => {
      clearInterval(interval);
    };
  }, [tickMs]);

  return useMemo(() => {
    if (!expiresAt || nowTs === null) {
      return null;
    }

    const expiresAtTs = Date.parse(expiresAt);
    if (Number.isNaN(expiresAtTs)) {
      return null;
    }

    return Math.ceil((expiresAtTs - nowTs) / 1000);
  }, [expiresAt, nowTs]);
}

