"use client";

import { Clock3 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import type { SecurityBlock } from "@/features/backoffice/security/types/security.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

function formatRemaining(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

export function SecurityBlockTimer({ block, t }: { block: SecurityBlock | null; t: Translator }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const label = useMemo(() => {
    if (!block) {
      return t("block.noActive");
    }
    if (block.status !== "active") {
      return t("block.expired");
    }
    if (!block.expires_at) {
      return t("block.indefinite");
    }
    const expiresMs = new Date(block.expires_at).getTime();
    if (!Number.isFinite(expiresMs) || expiresMs <= now) {
      return t("block.expired");
    }
    return t("block.remaining", { value: formatRemaining(expiresMs - now) });
  }, [block, now, t]);

  const tone = !block || block.status !== "active" ? "gray" : block.expires_at ? "warning" : "error";
  return (
    <StatusChip tone={tone} palette="countdown" icon={Clock3}>
      {label}
    </StatusChip>
  );
}
