export type BackofficeUser = {
  id: string;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  preferred_language: "uk" | "ru" | "en";
  is_staff: boolean;
  is_superuser: boolean;
};

export type BackofficeActionResponse = {
  mode: "sync" | "async";
  task_id?: string;
  run_id?: string;
  status?: string;
  result?: Record<string, unknown>;
  results?: Array<Record<string, unknown>>;
  sources?: number;
  stats?: Record<string, unknown>;
};
