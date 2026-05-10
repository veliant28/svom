"use client";

import { Clipboard, Eye, History, MoreHorizontal, Unlock } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { ActionIconButton } from "@/features/backoffice/components/widgets/action-icon-button";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { SecurityStatusBadge, SecurityThreatBadge, SourceKindBadges } from "@/features/backoffice/security/components/security-badges";
import { SecurityBlockTimer } from "@/features/backoffice/security/components/security-timer";
import type { SecurityActor, SecurityBlock } from "@/features/backoffice/security/types/security.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

function ClientCell({ actor, t }: { actor: SecurityActor; t: Translator }) {
  const label = actor.email_snapshot || actor.login_snapshot || actor.user_label;
  if (label) {
    return (
      <div className="min-w-0">
        <p className="truncate font-medium">{label}</p>
        {actor.user ? <p className="truncate text-xs" style={{ color: "var(--muted)" }}>{t("table.userId", { id: actor.user })}</p> : null}
      </div>
    );
  }
  return (
    <div className="min-w-0">
      <p className="truncate font-medium">{t("table.anonymous")}</p>
      <p className="truncate text-xs" style={{ color: "var(--muted)" }}>{t("table.fingerprint")}</p>
    </div>
  );
}

function MoreActions({
  actor,
  t,
  onWhitelist,
  onExtend,
  onCopy,
  onComment,
  onFalsePositive,
}: {
  actor: SecurityActor;
  t: Translator;
  onWhitelist: (actor: SecurityActor) => void;
  onExtend: (actor: SecurityActor) => void;
  onCopy: (actor: SecurityActor) => void;
  onComment: (actor: SecurityActor) => void;
  onFalsePositive: (actor: SecurityActor) => void;
}) {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [menuPosition, setMenuPosition] = useState<{ left: number; top: number } | null>(null);
  const itemClass = "block w-full px-3 py-2 text-left text-sm hover:bg-slate-100";

  useEffect(() => {
    if (!open) {
      setMenuPosition(null);
      return;
    }

    function updatePosition() {
      if (!buttonRef.current) {
        return;
      }
      const trigger = buttonRef.current.getBoundingClientRect();
      const menuWidth = menuRef.current?.offsetWidth ?? 208;
      const menuHeight = menuRef.current?.offsetHeight ?? 220;
      const left = Math.max(8, Math.min(trigger.right - menuWidth, window.innerWidth - menuWidth - 8));
      const top = Math.max(8, Math.min(trigger.bottom + 8, window.innerHeight - menuHeight - 8));
      setMenuPosition({ left, top });
    }

    updatePosition();

    function handlePointerDown(event: MouseEvent | TouchEvent) {
      const target = event.target as Node;
      const isOnButton = buttonRef.current?.contains(target);
      const isOnMenu = menuRef.current?.contains(target);
      if (!isOnButton && !isOnMenu) {
        setOpen(false);
      }
    }
    function handleWindowUpdate() {
      updatePosition();
    }
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("touchstart", handlePointerDown);
    window.addEventListener("resize", handleWindowUpdate);
    window.addEventListener("scroll", handleWindowUpdate, true);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("touchstart", handlePointerDown);
      window.removeEventListener("resize", handleWindowUpdate);
      window.removeEventListener("scroll", handleWindowUpdate, true);
    };
  }, [open]);

  const menu = open && typeof document !== "undefined"
    ? createPortal(
      <div
        ref={menuRef}
        className="fixed z-[1700] w-52 overflow-hidden rounded-lg border shadow-lg"
        style={{
          left: `${menuPosition?.left ?? 8}px`,
          top: `${menuPosition?.top ?? 8}px`,
          borderColor: "var(--border)",
          backgroundColor: "var(--surface)",
          visibility: menuPosition ? "visible" : "hidden",
        }}
      >
        {actor.active_block ? <button type="button" className={itemClass} onClick={() => { setOpen(false); onWhitelist(actor); }}>{t("actions.whitelist")}</button> : null}
        {actor.active_block ? <button type="button" className={itemClass} onClick={() => { setOpen(false); onExtend(actor); }}>{t("actions.extend")}</button> : null}
        <button type="button" className={itemClass} onClick={() => { setOpen(false); onCopy(actor); }}>{t("actions.copyIp")}</button>
        <button type="button" className={itemClass} onClick={() => { setOpen(false); onComment(actor); }}>{t("actions.comment")}</button>
        <button type="button" className={itemClass} onClick={() => { setOpen(false); onFalsePositive(actor); }}>{t("actions.falsePositive")}</button>
      </div>,
      document.body,
    )
    : null;

  return (
    <div className="relative">
      <BackofficeTooltip content={t("actions.more")} placement="top" align="end" tooltipClassName="whitespace-nowrap">
        <button
          ref={buttonRef}
          type="button"
          className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          aria-label={t("actions.more")}
          onClick={() => setOpen((prev) => !prev)}
        >
          <MoreHorizontal className="size-4" />
        </button>
      </BackofficeTooltip>
      {menu}
    </div>
  );
}

export function SecurityCenterTable({
  rows,
  totalCount,
  page,
  pagesCount,
  isLoading,
  error,
  t,
  onPageChange,
  onOpenDetails,
  onOpenHistory,
  onRelease,
  onWhitelist,
  onExtend,
  onCopy,
  onComment,
  onFalsePositive,
  onReblock,
}: {
  rows: SecurityActor[];
  totalCount: number;
  page: number;
  pagesCount: number;
  isLoading: boolean;
  error: string | null;
  t: Translator;
  onPageChange: (page: number) => void;
  onOpenDetails: (actor: SecurityActor) => void;
  onOpenHistory: (actor: SecurityActor) => void;
  onRelease: (block: SecurityBlock) => void;
  onWhitelist: (actor: SecurityActor) => void;
  onExtend: (actor: SecurityActor) => void;
  onCopy: (actor: SecurityActor) => void;
  onComment: (actor: SecurityActor) => void;
  onFalsePositive: (actor: SecurityActor) => void;
  onReblock: (actor: SecurityActor) => void;
}) {
  const columns = useMemo(() => [
    {
      key: "status",
      label: t("table.columns.status"),
      className: "w-[13%]",
      render: (actor: SecurityActor) => <SecurityStatusBadge status={actor.status} t={t} onClick={() => onOpenHistory(actor)} />,
    },
    {
      key: "source",
      label: t("table.columns.source"),
      className: "w-[22%]",
      render: (actor: SecurityActor) => (
        <div className="min-w-0">
          <div className="flex items-center gap-1">
            <SourceKindBadges actor={actor} t={t} primaryOnly className="shrink-0" />
            <p className="truncate font-semibold">{actor.source_ip || actor.source_identifier}</p>
          </div>
        </div>
      ),
    },
    { key: "client", label: t("table.columns.client"), className: "w-[17%]", render: (actor: SecurityActor) => <ClientCell actor={actor} t={t} /> },
    { key: "threat", label: t("table.columns.threat"), className: "w-[12%]", render: (actor: SecurityActor) => <SecurityThreatBadge level={actor.threat_level} t={t} /> },
    {
      key: "block",
      label: t("table.columns.block"),
      className: "w-[18%]",
      render: (actor: SecurityActor) => (
        <SecurityBlockTimer block={actor.active_block} t={t} />
      ),
    },
    {
      key: "actions",
      label: t("table.columns.actions"),
      className: "relative w-[18%]",
      render: (actor: SecurityActor) => (
        <div className="flex flex-wrap justify-end gap-1">
          <ActionIconButton label={t("actions.view")} icon={Eye} onClick={() => onOpenDetails(actor)} />
          <ActionIconButton label={t("actions.history")} icon={History} onClick={() => onOpenHistory(actor)} />
          <ActionIconButton label={t("actions.copyIp")} icon={Clipboard} onClick={() => onCopy(actor)} />
          <BackofficeTooltip content={actor.active_block ? t("actions.release") : t("actions.reblock")} placement="top" align="center" wrapperClassName="inline-flex">
            <button
              type="button"
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border transition-colors"
              aria-label={actor.active_block ? t("actions.release") : t("actions.reblock")}
              style={{
                borderColor: actor.active_block ? "#16a34a" : "var(--border)",
                backgroundColor: actor.active_block ? "#16a34a" : "var(--surface)",
                color: actor.active_block ? "#ffffff" : "var(--text)",
              }}
              onClick={() => (actor.active_block ? onRelease(actor.active_block) : onReblock(actor))}
            >
              <Unlock className="size-4" />
            </button>
          </BackofficeTooltip>
          <MoreActions
            actor={actor}
            t={t}
            onWhitelist={onWhitelist}
            onExtend={onExtend}
            onCopy={onCopy}
            onComment={onComment}
            onFalsePositive={onFalsePositive}
          />
        </div>
      ),
    },
  ], [onComment, onCopy, onExtend, onFalsePositive, onOpenDetails, onOpenHistory, onReblock, onRelease, onWhitelist, t]);

  return (
    <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={t("empty.center")}>
      <div className="overflow-visible">
        <BackofficeTable noHorizontalScroll rows={rows} columns={columns} emptyLabel={t("empty.center")} getRowKey={(row) => row.id} />
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs" style={{ color: "var(--muted)" }}>
        <span>{t("pagination.total", { count: totalCount })}</span>
        <div className="flex items-center gap-2">
          <button type="button" className="h-8 rounded-md border px-2" style={{ borderColor: "var(--border)" }} disabled={page <= 1} onClick={() => onPageChange(Math.max(1, page - 1))}>{t("pagination.prev")}</button>
          <span>{t("pagination.page", { current: page, total: pagesCount })}</span>
          <button type="button" className="h-8 rounded-md border px-2" style={{ borderColor: "var(--border)" }} disabled={page >= pagesCount} onClick={() => onPageChange(Math.min(pagesCount, page + 1))}>{t("pagination.next")}</button>
        </div>
      </div>
    </AsyncState>
  );
}
