type Translator = (key: string, values?: Record<string, string | number>) => string;

export function maskedTokenView(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  const compact = value.replace(/\s+/g, "").trim();
  if (!compact) {
    return "-";
  }

  if (compact.includes("...")) {
    return compact.replace("...", ".".repeat(15));
  }

  if (compact.length <= 24) {
    return compact;
  }

  const start = compact.slice(0, 10);
  const end = compact.slice(-8);
  return `${start}${".".repeat(15)}${end}`;
}

export function formatSupplierTokenCountdown(secondsLeft: number | null, tAuth: Translator): string {
  if (secondsLeft === null) {
    return tAuth("status.countdownUnavailable");
  }
  if (secondsLeft <= 0) {
    return tAuth("status.countdownExpired");
  }
  if (secondsLeft < 60) {
    return tAuth("status.countdownLessThanMinute");
  }
  if (secondsLeft < 3600) {
    return tAuth("status.countdownMinutes", { minutes: Math.floor(secondsLeft / 60) });
  }
  if (secondsLeft < 86400) {
    const hours = Math.floor(secondsLeft / 3600);
    const minutes = Math.floor((secondsLeft % 3600) / 60);
    return tAuth("status.countdownHoursMinutes", { hours, minutes });
  }
  const days = Math.floor(secondsLeft / 86400);
  const hours = Math.floor((secondsLeft % 86400) / 3600);
  return tAuth("status.countdownDaysHours", { days, hours });
}
