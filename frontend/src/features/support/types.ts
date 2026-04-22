export type SupportUser = {
  id: number;
  email: string;
  full_name: string;
  is_online: boolean;
};

export type SupportThreadStatus = "new" | "open" | "resolved" | "closed";
export type SupportPriority = "low" | "normal" | "high";
export type SupportMessageKind = "message" | "system_event";
export type SupportAuthorSide = "customer" | "staff" | "system";

export type SupportMessage = {
  id: string;
  thread_id: string;
  author: SupportUser | null;
  author_side: SupportAuthorSide;
  kind: SupportMessageKind;
  body: string;
  event_code: string;
  event_payload: Record<string, unknown>;
  created_at: string;
  edited_at: string | null;
};

export type SupportThread = {
  id: string;
  subject: string;
  status: SupportThreadStatus;
  priority: SupportPriority;
  customer: SupportUser;
  assigned_staff: SupportUser | null;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
  first_response_at: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  latest_message_id: string | null;
  latest_message_preview: string;
  latest_message_author_side: string;
  is_waiting: boolean;
  unread_count?: number;
  is_mine?: boolean;
};

export type SupportMessagesPage = {
  results: SupportMessage[];
  has_more: boolean;
  next_before_message_id: string | null;
};

export type SupportCounters = {
  user_id: number;
  total_unread_threads: number;
  assigned_to_me?: number;
  unassigned?: number;
  open_threads?: number;
};

export type SupportQueueSnapshot = {
  new: number;
  open: number;
  waiting_for_support: number;
  waiting_for_client: number;
  resolved: number;
  closed: number;
  unassigned: number;
  latest_threads: SupportThread[];
};

export type SupportWallboardOperator = {
  user: SupportUser;
  active_threads: number;
};

export type SupportWallboardSnapshot = {
  counts: {
    new: number;
    open: number;
    waiting_for_support: number;
    waiting_for_client: number;
    resolved: number;
    closed: number;
    unassigned: number;
    online_operators: number;
    active_threads: number;
  };
  threads_per_operator: SupportWallboardOperator[];
  oldest_waiting: SupportThread | null;
  latest_active_threads: SupportThread[];
  avg_first_response_seconds: number | null;
};

export type SupportTypingPayload = {
  thread_id: string;
  customer_users: SupportUser[];
  staff_users: SupportUser[];
};

export type SupportBootstrap = {
  threads: SupportThread[];
  selected_thread: SupportThread | null;
  messages: SupportMessagesPage | null;
  counters: SupportCounters;
  queue?: SupportQueueSnapshot;
  wallboard?: SupportWallboardSnapshot;
};

export type SupportThreadFilters = {
  status?: SupportThreadStatus | "";
  assigned_to_me?: boolean;
  unassigned?: boolean;
  waiting?: boolean;
  search?: string;
  ordering?: "last_message_at" | "-last_message_at" | "created_at" | "-created_at" | "priority" | "-priority";
  limit?: number;
  thread_id?: string;
};

export type SupportRealtimeEvent =
  | { type: "support.connection.ready"; payload: { counters?: SupportCounters } }
  | { type: "support.thread.bootstrap"; payload: { thread_id: string; typing: SupportTypingPayload; assigned_staff: SupportUser | null } }
  | { type: "support.thread.created"; payload: { thread: SupportThread } }
  | { type: "support.thread.updated"; payload: { thread: SupportThread } }
  | { type: "support.thread.status_changed"; payload: { thread: SupportThread; status?: SupportThreadStatus } }
  | { type: "support.thread.assigned"; payload: { thread: SupportThread; assigned_staff?: SupportUser | null } }
  | { type: "support.thread.reassigned"; payload: { thread: SupportThread; assigned_staff?: SupportUser | null } }
  | { type: "support.thread.read"; payload: { thread_id: string; reader_id?: number; last_read_message_id?: string | null; last_read_at?: string | null } }
  | { type: "support.message.created"; payload: { thread_id: string; message: SupportMessage } }
  | { type: "support.typing.updated"; payload: SupportTypingPayload }
  | { type: "support.presence.updated"; payload: { thread_id?: string; role: string; online: boolean; user: SupportUser } }
  | { type: "support.counters.updated"; payload: SupportCounters }
  | { type: "support.queue.updated"; payload: SupportQueueSnapshot }
  | { type: "support.wallboard.updated"; payload: SupportWallboardSnapshot };
