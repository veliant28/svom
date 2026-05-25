export type BackofficeWorkerStatus = "active" | "idle" | "stuck" | "offline";

export type BackofficeWorker = {
  name: string;
  cpu_percent: number;
  active_count: number;
  reserved_count: number;
  scheduled_count: number;
  longest_task_seconds: number;
  total_tasks_processed: number;
  online: boolean;
  stuck: boolean;
  status: BackofficeWorkerStatus;
  last_seen_at: string;
  last_heartbeat_at: string;
  pool_processes: number[];
  current_task_ids: string[];
  current_task_names: string[];
  queues: string[];
};

export type BackofficeWorkerCpuHistorySample = {
  timestamp: string;
  workers: Record<string, number>;
};

export type BackofficeWorkersDashboard = {
  generated_at: string;
  workers: BackofficeWorker[];
  status_counts: {
    active: number;
    idle: number;
    stuck: number;
    offline: number;
  };
  cpu_history: BackofficeWorkerCpuHistorySample[];
};

export type BackofficeWorkerAction = "stop" | "pause" | "resume" | "restart" | "kill_task";

export type BackofficeWorkerActionResponse = {
  status: "ok" | "error";
  action: BackofficeWorkerAction;
  worker?: string;
  task_id?: string;
  detail?: string;
  queues?: string[];
  reply?: unknown;
};
