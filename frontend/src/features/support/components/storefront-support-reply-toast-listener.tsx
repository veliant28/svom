"use client";

import { useCallback, useEffect, useRef } from "react";
import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { useSupportSocket } from "@/features/support/hooks/use-support-socket";
import type { SupportRealtimeEvent, SupportThread } from "@/features/support/types";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

const MAX_TRACKED_MESSAGE_IDS = 200;

function extractThread(event: SupportRealtimeEvent): SupportThread | null {
  if (
    event.type === "support.thread.created"
    || event.type === "support.thread.updated"
    || event.type === "support.thread.status_changed"
    || event.type === "support.thread.assigned"
    || event.type === "support.thread.reassigned"
  ) {
    return event.payload.thread;
  }
  return null;
}

function trimOldMessageIds(cache: Set<string>) {
  while (cache.size > MAX_TRACKED_MESSAGE_IDS) {
    const oldest = cache.values().next().value;
    if (!oldest) {
      break;
    }
    cache.delete(oldest);
  }
}

export function StorefrontSupportReplyToastListener() {
  const t = useTranslations("commerce.support");
  const { token, isAuthenticated, user } = useAuth();
  const { showInfo } = useStorefrontFeedback();
  const threadLastMessageRef = useRef<Map<string, string>>(new Map());
  const shownMessageIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    threadLastMessageRef.current.clear();
    shownMessageIdsRef.current.clear();
  }, [token, user?.id]);

  const handleEvent = useCallback(
    (event: SupportRealtimeEvent) => {
      const thread = extractThread(event);
      if (!thread) {
        return;
      }

      const latestMessageId = String(thread.latest_message_id || "").trim();
      if (!latestMessageId) {
        return;
      }

      const previousMessageId = threadLastMessageRef.current.get(thread.id);
      threadLastMessageRef.current.set(thread.id, latestMessageId);
      if (previousMessageId === latestMessageId) {
        return;
      }

      if (thread.latest_message_author_side !== "staff") {
        return;
      }
      if (Number(thread.unread_count || 0) <= 0) {
        return;
      }
      if (shownMessageIdsRef.current.has(latestMessageId)) {
        return;
      }

      shownMessageIdsRef.current.add(latestMessageId);
      trimOldMessageIds(shownMessageIdsRef.current);

      const subject = String(thread.subject || "").trim();
      if (subject) {
        showInfo(t("messages.replyReceivedWithSubject", { subject }));
        return;
      }
      showInfo(t("messages.replyReceived"));
    },
    [showInfo, t],
  );

  useSupportSocket({
    token,
    path: "/ws/support/user/",
    enabled: isAuthenticated && Boolean(token),
    onEvent: handleEvent,
  });

  return null;
}
