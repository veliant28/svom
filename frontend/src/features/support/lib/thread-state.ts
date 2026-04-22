import type { SupportMessage, SupportThread } from "@/features/support/types";

export function upsertThread(threads: SupportThread[], nextThread: SupportThread): SupportThread[] {
  const rest = threads.filter((thread) => thread.id !== nextThread.id);
  return [nextThread, ...rest].sort((left, right) => {
    const leftTime = new Date(left.last_message_at || left.created_at).getTime();
    const rightTime = new Date(right.last_message_at || right.created_at).getTime();
    return rightTime - leftTime;
  });
}

export function mergeMessages(messages: SupportMessage[], incoming: SupportMessage[]): SupportMessage[] {
  const byId = new Map<string, SupportMessage>();
  for (const message of messages) {
    byId.set(message.id, message);
  }
  for (const message of incoming) {
    byId.set(message.id, message);
  }
  return Array.from(byId.values()).sort((left, right) => {
    const leftTime = new Date(left.created_at).getTime();
    const rightTime = new Date(right.created_at).getTime();
    if (leftTime !== rightTime) {
      return leftTime - rightTime;
    }
    return left.id.localeCompare(right.id);
  });
}

export function mergeThreadLists(current: SupportThread[], incoming: SupportThread[]): SupportThread[] {
  const byId = new Map<string, SupportThread>();
  for (const thread of current) {
    byId.set(thread.id, thread);
  }
  for (const thread of incoming) {
    byId.set(thread.id, thread);
  }
  return Array.from(byId.values()).sort((left, right) => {
    const leftTime = new Date(left.last_message_at || left.created_at).getTime();
    const rightTime = new Date(right.last_message_at || right.created_at).getTime();
    return rightTime - leftTime;
  });
}
