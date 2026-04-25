type TimingContext = Record<string, string | number | boolean | undefined>;

function isTimingEnabled(): boolean {
  if (typeof window !== "undefined") {
    return false;
  }

  const raw = process.env.NEXT_SSR_TIMING_LOG_ENABLED ?? process.env.SVOM_FRONTEND_TIMING_LOGS ?? "0";
  return ["1", "true", "yes", "on"].includes(raw.trim().toLowerCase());
}

export function createRequestTimingId(prefix = "ssr"): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }

  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function logServerTiming(label: string, startedAt: number, context: TimingContext = {}): void {
  if (!isTimingEnabled()) {
    return;
  }

  const payload = {
    label,
    duration_ms: Math.round((performance.now() - startedAt) * 100) / 100,
    ...context,
  };

  console.info(`frontend_ssr_timing ${JSON.stringify(payload)}`);
}

export async function timeServerAsync<T>(
  label: string,
  callback: () => Promise<T>,
  context: TimingContext = {},
): Promise<T> {
  const startedAt = performance.now();
  try {
    return await callback();
  } finally {
    logServerTiming(label, startedAt, context);
  }
}
