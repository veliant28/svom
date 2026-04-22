"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, LoaderCircle, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";

import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useAuth } from "@/features/auth/hooks/use-auth";
import {
  assignSupportThread,
  getSupportBootstrap,
  getSupportMessages,
  getSupportStaffOptions,
  markSupportThreadRead,
  postSupportMessage,
  updateSupportThreadStatus,
} from "@/features/support/api/support-api";
import { SupportComposer } from "@/features/support/components/support-composer";
import { SupportThreadDetails } from "@/features/support/components/support-thread-details";
import { SupportThreadFeed } from "@/features/support/components/support-thread-feed";
import { SupportThreadList } from "@/features/support/components/support-thread-list";
import { useSupportSocket } from "@/features/support/hooks/use-support-socket";
import { mergeMessages, mergeThreadLists, upsertThread } from "@/features/support/lib/thread-state";
import type {
  SupportMessage,
  SupportRealtimeEvent,
  SupportThread,
  SupportThreadStatus,
  SupportTypingPayload,
  SupportUser,
} from "@/features/support/types";

const STATUS_OPTIONS: SupportThreadStatus[] = ["new", "open", "resolved", "closed"];

export function SupportPage() {
  const t = useTranslations("backoffice.common.support");
  const { token } = useAuth();
  const { showApiError, showSuccess } = useBackofficeFeedback();
  const [threads, setThreads] = useState<SupportThread[]>([]);
  const [messages, setMessages] = useState<SupportMessage[]>([]);
  const [staffOptions, setStaffOptions] = useState<SupportUser[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [typing, setTyping] = useState<SupportTypingPayload | null>(null);
  const [search, setSearch] = useState("");
  const [waitingOnly, setWaitingOnly] = useState(false);
  const [assignedToMe, setAssignedToMe] = useState(false);
  const [unassignedOnly, setUnassignedOnly] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);

  const selectedThread = useMemo(
    () => threads.find((thread) => thread.id === selectedThreadId) ?? null,
    [selectedThreadId, threads],
  );

  const loadThreads = useCallback(async () => {
    if (!token) {
      return;
    }
    setIsLoading(true);
    try {
      const bootstrap = await getSupportBootstrap(token, "backoffice", {
        limit: 30,
        thread_id: selectedThreadId || undefined,
        search,
        waiting: waitingOnly,
        assigned_to_me: assignedToMe,
        unassigned: unassignedOnly,
      });
      setThreads(bootstrap.threads);
      const nextSelected = bootstrap.selected_thread?.id || bootstrap.threads[0]?.id || null;
      setSelectedThreadId(nextSelected);
      setMessages(bootstrap.messages?.results || []);
    } catch (error) {
      showApiError(error, t("messages.loadFailed"));
    } finally {
      setIsLoading(false);
    }
  }, [assignedToMe, search, selectedThreadId, showApiError, t, token, unassignedOnly, waitingOnly]);

  useEffect(() => {
    void loadThreads();
  }, [loadThreads]);

  useEffect(() => {
    if (!token) {
      return;
    }
    const authToken: string = token;
    let mounted = true;
    async function loadStaff() {
      try {
        const response = await getSupportStaffOptions(authToken);
        if (mounted) {
          setStaffOptions(response.results);
        }
      } catch (error) {
        if (mounted) {
          showApiError(error, t("messages.loadStaffFailed"));
        }
      }
    }
    void loadStaff();
    return () => {
      mounted = false;
    };
  }, [showApiError, t, token]);

  useEffect(() => {
    if (!token || !selectedThreadId) {
      return;
    }
    const authToken: string = token;
    const threadId: string = selectedThreadId;
    let mounted = true;
    async function openThread() {
      try {
        const response = await getSupportMessages(authToken, "backoffice", threadId, { limit: 50 });
        const page = await markSupportThreadRead(authToken, "backoffice", threadId);
        if (!mounted) {
          return;
        }
        setMessages(response.results);
        setThreads((current) => current.map((thread) => (thread.id === page.thread_id ? { ...thread, unread_count: 0 } : thread)));
      } catch (error) {
        if (mounted) {
          showApiError(error, t("messages.loadFailed"));
        }
      }
    }
    void openThread();
    return () => {
      mounted = false;
    };
  }, [selectedThreadId, showApiError, t, token]);

  function handleUserEvent(event: SupportRealtimeEvent) {
    if (
      event.type === "support.thread.created"
      || event.type === "support.thread.updated"
      || event.type === "support.thread.status_changed"
      || event.type === "support.thread.assigned"
      || event.type === "support.thread.reassigned"
    ) {
      setThreads((current) => upsertThread(current, event.payload.thread));
    }
  }

  function handleQueueEvent(event: SupportRealtimeEvent) {
    if (event.type === "support.queue.updated") {
      setThreads((current) => mergeThreadLists(current, event.payload.latest_threads));
      return;
    }
    if (event.type === "support.presence.updated" && selectedThread?.assigned_staff?.id === event.payload.user.id) {
      setThreads((current) => current.map((thread) => (
        thread.id === selectedThread.id && thread.assigned_staff
          ? { ...thread, assigned_staff: { ...thread.assigned_staff, is_online: event.payload.online } }
          : thread
      )));
    }
  }

  function handleThreadEvent(event: SupportRealtimeEvent) {
    if (event.type === "support.message.created" && event.payload.thread_id === selectedThreadId) {
      setMessages((current) => mergeMessages(current, [event.payload.message]));
      return;
    }
    if (event.type === "support.typing.updated") {
      setTyping(event.payload);
      return;
    }
    if (
      event.type === "support.thread.updated"
      || event.type === "support.thread.status_changed"
      || event.type === "support.thread.assigned"
      || event.type === "support.thread.reassigned"
    ) {
      setThreads((current) => upsertThread(current, event.payload.thread));
    }
  }

  const userSocket = useSupportSocket({ token, path: "/ws/support/user/", enabled: Boolean(token), onEvent: handleUserEvent });
  const queueSocket = useSupportSocket({ token, path: "/ws/support/queue/", enabled: Boolean(token), onEvent: handleQueueEvent });
  const threadSocket = useSupportSocket({
    token,
    path: selectedThreadId ? `/ws/support/threads/${selectedThreadId}/` : null,
    enabled: Boolean(token && selectedThreadId),
    onEvent: handleThreadEvent,
  });

  const isRealtimeConnected = userSocket.connectionState === "open"
    && queueSocket.connectionState === "open"
    && (!selectedThreadId || threadSocket.connectionState === "open");

  async function handleSend(body: string) {
    if (!token || !selectedThreadId) {
      return;
    }
    const optimistic: SupportMessage = {
      id: `temp-${Date.now()}`,
      thread_id: selectedThreadId,
      author: selectedThread?.assigned_staff || null,
      author_side: "staff",
      kind: "message",
      body,
      event_code: "",
      event_payload: {},
      created_at: new Date().toISOString(),
      edited_at: null,
    };
    setIsSending(true);
    setMessages((current) => mergeMessages(current, [optimistic]));
    try {
      const response = await postSupportMessage(token, "backoffice", selectedThreadId, body);
      setMessages((current) => mergeMessages(current.filter((message) => message.id !== optimistic.id), response.results));
    } catch (error) {
      setMessages((current) => current.filter((message) => message.id !== optimistic.id));
      showApiError(error, t("messages.sendFailed"));
    } finally {
      setIsSending(false);
    }
  }

  async function handleAssign(assignedStaffId: number) {
    if (!token || !selectedThreadId) {
      return;
    }
    try {
      const thread = await assignSupportThread(token, selectedThreadId, assignedStaffId);
      setThreads((current) => upsertThread(current, thread));
      showSuccess(t("messages.assigned"));
    } catch (error) {
      showApiError(error, t("messages.assignFailed"));
    }
  }

  async function handleStatusChange(status: SupportThreadStatus) {
    if (!token || !selectedThreadId) {
      return;
    }
    try {
      const thread = await updateSupportThreadStatus(token, selectedThreadId, status);
      setThreads((current) => upsertThread(current, thread));
      showSuccess(t("messages.statusChanged"));
    } catch (error) {
      showApiError(error, t("messages.statusFailed"));
    }
  }

  return (
    <section className="grid min-w-0 gap-4 overflow-x-hidden">
      <PageHeader
        title={t("title")}
        description={t("subtitle")}
        actions={(
          <div className="inline-flex items-center gap-2">
            <BackofficeStatusChip
              tone={isRealtimeConnected ? "success" : "warning"}
              icon={isRealtimeConnected ? CheckCircle2 : LoaderCircle}
              className={isRealtimeConnected ? "" : "animate-pulse"}
            >
              {isRealtimeConnected ? t("states.realtimeConnected") : t("states.realtimeReconnecting")}
            </BackofficeStatusChip>
            <button
              type="button"
              className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-70"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              disabled={isLoading}
              onClick={() => {
                void loadThreads();
              }}
            >
              <RefreshCw size={16} className="animate-spin" style={{ animationDuration: "2.2s" }} />
              {t("actions.refresh")}
            </button>
          </div>
        )}
      />

      <div className="flex flex-wrap gap-2 rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("filters.search")} className="h-10 w-full min-w-0 rounded-md border px-3 text-sm sm:w-72" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }} />
        <label className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <input className="size-4" type="checkbox" checked={waitingOnly} onChange={(event) => setWaitingOnly(event.target.checked)} />
          {t("filters.waiting")}
        </label>
        <label className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <input className="size-4" type="checkbox" checked={assignedToMe} onChange={(event) => setAssignedToMe(event.target.checked)} />
          {t("filters.assignedToMe")}
        </label>
        <label className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <input className="size-4" type="checkbox" checked={unassignedOnly} onChange={(event) => setUnassignedOnly(event.target.checked)} />
          {t("filters.unassigned")}
        </label>
      </div>

      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(280px,340px)_minmax(0,1fr)_minmax(260px,300px)]">
        <SupportThreadList mode="staff" items={threads} selectedThreadId={selectedThreadId} onSelect={setSelectedThreadId} emptyLabel={isLoading ? t("states.loading") : t("states.emptyThreads")} />
        <div className="flex min-h-[680px] min-w-0 flex-col gap-4">
          <SupportThreadFeed currentSide="staff" messages={messages} typing={typing} emptyLabel={t("states.emptyMessages")} />
          <SupportComposer
            disabled={!selectedThreadId || !threadSocket.isConnected}
            isSending={isSending}
            placeholder={t("composer.placeholder")}
            sendLabel={t("composer.send")}
            sendingLabel={t("composer.sending")}
            onTypingStart={() => {
              threadSocket.send({ type: "support.typing.start" });
            }}
            onTypingStop={() => {
              threadSocket.send({ type: "support.typing.stop" });
            }}
            onSend={handleSend}
          />
        </div>
        <div className="grid min-w-0 gap-4">
          <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
            <p className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>{t("details.actions")}</p>
            <div className="mt-3 grid gap-3">
              <select
                value={selectedThread?.status || ""}
                onChange={(event) => {
                  void handleStatusChange(event.target.value as SupportThreadStatus);
                }}
                className="h-10 rounded-lg border px-3 text-sm"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                disabled={!selectedThreadId}
              >
                <option value="">{t("details.selectStatus")}</option>
                {STATUS_OPTIONS.map((status) => (
                  <option key={status} value={status}>
                    {t(`statuses.${status}`)}
                  </option>
                ))}
              </select>
              <select
                value={selectedThread?.assigned_staff?.id || ""}
                onChange={(event) => {
                  const staffId = Number(event.target.value);
                  if (Number.isFinite(staffId)) {
                    void handleAssign(staffId);
                  }
                }}
                className="h-10 rounded-lg border px-3 text-sm"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                disabled={!selectedThreadId}
              >
                <option value="">{t("details.selectAssignee")}</option>
                {staffOptions.map((user) => <option key={user.id} value={user.id}>{user.full_name}</option>)}
              </select>
            </div>
          </div>
          <SupportThreadDetails thread={selectedThread} />
        </div>
      </div>
    </section>
  );
}
