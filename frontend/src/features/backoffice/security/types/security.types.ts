import type { BackofficeListQuery } from "@/features/backoffice/api/backoffice-api.types";

export type SecurityStatus = "suspicious" | "blocked" | "whitelisted" | "unblocked" | "expired" | "error";
export type SecurityThreatLevel = "low" | "medium" | "high" | "critical";
export type SecuritySourceKind = "ipv4" | "ipv6" | "unknown";

export type SecurityBlock = {
  id: string;
  actor: string;
  actor_source: string;
  actor_status: SecurityStatus;
  actor_threat_level: SecurityThreatLevel;
  block_type: string;
  value: string;
  status: "active" | "released" | "expired";
  reason: string;
  comment: string;
  is_automatic: boolean;
  block_mode: "soft" | "hard";
  blocked_by_label: string;
  released_by_label: string;
  blocked_at: string;
  expires_at: string | null;
  released_at: string | null;
  release_reason: string;
  metadata: Record<string, unknown>;
};

export type SecurityActor = {
  id: string;
  source_ip: string | null;
  source_identifier: string;
  source_kind: SecuritySourceKind;
  source_flags: string[];
  user: number | null;
  user_label: string;
  login_snapshot: string;
  email_snapshot: string;
  threat_level: SecurityThreatLevel;
  threat_score: number | null;
  status: SecurityStatus;
  block_count: number;
  first_seen_at: string | null;
  last_seen_at: string | null;
  last_blocked_at: string | null;
  last_unblocked_at: string | null;
  active_block: SecurityBlock | null;
  metadata: Record<string, unknown>;
};

export type SecurityEvent = {
  id: string;
  actor_id: string | null;
  created_at: string;
  event_type: string;
  severity: string;
  source_ip: string | null;
  source_kind: string;
  actor_source: string;
  user_label: string;
  login_snapshot: string;
  email_snapshot: string;
  method: string;
  endpoint: string;
  status_code: number | null;
  user_agent: string;
  fingerprint: string;
  session_key: string;
  rule: string;
  metadata: Record<string, unknown>;
  actor_type: string;
  actor_user_label: string;
};

export type SecurityActorDetail = {
  actor: SecurityActor;
  active_block: SecurityBlock | null;
  activity_summary: Record<
    "requests_5m" | "requests_1h" | "requests_24h" | "status_429" | "status_403" | "status_401" | "status_500" | "failed_login" | "password_reset" | "checkout",
    number
  >;
  recent_events: SecurityEvent[];
  top_endpoints: Array<{ endpoint: string; requests: number; last_status_code: number | null }>;
};

export type SecuritySummary = {
  kpis: Record<"active_blocks" | "suspicious_sources" | "blocked_24h" | "failed_logins" | "rate_limit_events" | "critical_threats", number>;
  latest_critical_events: SecurityEvent[];
  active_blocks: SecurityBlock[];
};

export type SecurityTimeseries = {
  events_by_hour: Array<{ bucket: string; total: number }>;
  events_by_type: Array<{ event_type: string; total: number }>;
  top_sources: Array<{ source_ip: string | null; total: number }>;
  top_endpoints: Array<{ endpoint: string; total: number }>;
};

export type SecurityActorsQuery = BackofficeListQuery & {
  status?: string;
  threat_level?: string;
};

export type SecurityPaginatedActors = {
  count: number;
  results: SecurityActor[];
};
