"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Headset, LoaderCircle, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { AccountAuthRequired } from "@/features/account/components/account-auth-required";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import {
  createSupportThread,
  getSupportBootstrap,
  getSupportMessages,
  markSupportThreadRead,
  postSupportMessage,
} from "@/features/support/api/support-api";
import { SupportComposer } from "@/features/support/components/support-composer";
import { SupportThreadDetails } from "@/features/support/components/support-thread-details";
import { SupportThreadFeed } from "@/features/support/components/support-thread-feed";
import { SupportThreadList } from "@/features/support/components/support-thread-list";
import { useSupportSocket } from "@/features/support/hooks/use-support-socket";
import { mergeMessages, upsertThread } from "@/features/support/lib/thread-state";
import type { SupportMessage, SupportRealtimeEvent, SupportThread, SupportTypingPayload } from "@/features/support/types";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

export function AccountSupportPage() {
  const t = useTranslations("commerce.support");
  const { token, isAuthenticated } = useAuth();
  const { showApiError, showSuccess } = useStorefrontFeedback();
  const [threads, setThreads] = useState<SupportThread[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<SupportMessage[]>([]);
  const [typing, setTyping] = useState<SupportTypingPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [subject, setSubject] = useState("");
  const [newMessageBody, setNewMessageBody] = useState("");

  const selectedThread = useMemo(
    () => threads.find((thread) => thread.id === selectedThreadId) ?? null,
    [selectedThreadId, threads],
  );

  const loadBootstrap = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setThreads([]);
      setSelectedThreadId(null);
      setMessages([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const response = await getSupportBootstrap(token, "storefront", { limit: 20, thread_id: selectedThreadId || undefined });
      setThreads(response.threads);
      const nextSelectedId = response.selected_thread?.id || response.threads[0]?.id || null;
      setSelectedThreadId(nextSelectedId);
      setMessages(response.messages?.results || []);
    } catch (error) {
      showApiError(error, t("states.error"));
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, selectedThreadId, showApiError, t, token]);

  useEffect(() => {
    void loadBootstrap();
  }, [loadBootstrap]);

  useEffect(() => {
    if (!token || !selectedThreadId) {
      return;
    }
    const authToken: string = token;
    const threadId: string = selectedThreadId;
    let mounted = true;
    async function loadThreadMessages() {
      try {
        const response = await getSupportMessages(authToken, "storefront", threadId, { limit: 50 });
        if (!mounted) {
          return;
        }
        setMessages(response.results);
        await markSupportThreadRead(authToken, "storefront", threadId);
        setThreads((current) => current.map((thread) => (thread.id === threadId ? { ...thread, unread_count: 0 } : thread)));
      } catch (error) {
        if (mounted) {
          showApiError(error, t("states.error"));
        }
      }
    }
    void loadThreadMessages();
    return () => {
      mounted = false;
    };
  }, [selectedThreadId, showApiError, t, token]);

  function handleUserEvent(event: SupportRealtimeEvent) {
    if (event.type === "support.thread.created" || event.type === "support.thread.updated" || event.type === "support.thread.status_changed" || event.type === "support.thread.assigned" || event.type === "support.thread.reassigned") {
      setThreads((current) => upsertThread(current, event.payload.thread));
      return;
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
    if (event.type === "support.thread.updated" || event.type === "support.thread.status_changed" || event.type === "support.thread.assigned" || event.type === "support.thread.reassigned") {
      setThreads((current) => upsertThread(current, event.payload.thread));
    }
  }

  const userSocket = useSupportSocket({
    token,
    path: "/ws/support/user/",
    enabled: isAuthenticated,
    onEvent: handleUserEvent,
  });

  const threadSocket = useSupportSocket({
    token,
    path: selectedThreadId ? `/ws/support/threads/${selectedThreadId}/` : null,
    enabled: isAuthenticated && Boolean(selectedThreadId),
    onEvent: handleThreadEvent,
  });

  const isRealtimeConnected = userSocket.connectionState === "open" && (!selectedThreadId || threadSocket.connectionState === "open");

  async function handleCreateThread() {
    if (!token) {
      return;
    }
    setIsSending(true);
    try {
      const thread = await createSupportThread(token, { subject: subject.trim(), body: newMessageBody.trim() });
      setThreads((current) => upsertThread(current, thread));
      setSelectedThreadId(thread.id);
      setSubject("");
      setNewMessageBody("");
      showSuccess(t("messages.threadCreated"));
      await loadBootstrap();
    } catch (error) {
      showApiError(error, t("messages.createFailed"));
    } finally {
      setIsSending(false);
    }
  }

  async function handleSend(body: string) {
    if (!token || !selectedThreadId) {
      return;
    }
    const optimistic: SupportMessage = {
      id: `temp-${Date.now()}`,
      thread_id: selectedThreadId,
      author: selectedThread?.customer || null,
      author_side: "customer",
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
      const response = await postSupportMessage(token, "storefront", selectedThreadId, body);
      setMessages((current) => mergeMessages(current.filter((message) => message.id !== optimistic.id), response.results));
    } catch (error) {
      setMessages((current) => current.filter((message) => message.id !== optimistic.id));
      showApiError(error, t("messages.sendFailed"));
    } finally {
      setIsSending(false);
    }
  }

  if (!isAuthenticated) {
    return <AccountAuthRequired title={t("title")} message={t("authRequired")} loginLabel={t("goToLogin")} />;
  }

  return (
    <section className="mx-auto w-full max-w-6xl min-w-0 overflow-x-hidden px-4 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">{t("title")}</h1>
          <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>{t("subtitle")}</p>
        </div>
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
              void loadBootstrap();
            }}
          >
            <RefreshCw size={16} className="animate-spin" style={{ animationDuration: "2.2s" }} />
            {t("actions.refresh")}
          </button>
        </div>
      </div>

      <div className="mt-4 rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <div className="grid gap-3 md:grid-cols-[240px_minmax(0,1fr)_auto]">
          <input value={subject} onChange={(event) => setSubject(event.target.value)} placeholder={t("create.subjectPlaceholder")} className="h-10 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }} />
          <input value={newMessageBody} onChange={(event) => setNewMessageBody(event.target.value)} placeholder={t("create.messagePlaceholder")} className="h-10 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }} />
          <button type="button" disabled={isSending || !subject.trim() || !newMessageBody.trim()} onClick={() => { void handleCreateThread(); }} className="inline-flex h-10 items-center justify-center rounded-md bg-blue-600 px-4 text-sm font-semibold text-white disabled:opacity-60">
            <Headset size={16} className="mr-2" />
            {t("actions.create")}
          </button>
        </div>
      </div>

      <div className="mt-4 grid min-w-0 gap-4 lg:grid-cols-[minmax(260px,320px)_minmax(0,1fr)_minmax(240px,280px)]">
        <SupportThreadList mode="customer" items={threads} selectedThreadId={selectedThreadId} onSelect={setSelectedThreadId} emptyLabel={isLoading ? t("states.loading") : t("states.emptyThreads")} />
        <div className="flex min-h-[560px] min-w-0 flex-col gap-4">
          <SupportThreadFeed currentSide="customer" messages={messages} typing={typing} emptyLabel={t("states.emptyMessages")} />
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
        <SupportThreadDetails thread={selectedThread} />
      </div>
    </section>
  );
}
