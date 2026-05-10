"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { RefreshCw } from "lucide-react";

import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { getSecurityActorDetails, getSecurityActorHistory, getSecurityActors, getSecuritySummary, getSecurityTimeseries } from "@/features/backoffice/security/api/security-api";
import { SecurityActionModal, type SecurityActionTarget } from "@/features/backoffice/security/components/security-action-modal";
import { SecurityCenterTable } from "@/features/backoffice/security/components/security-center-table";
import { SecurityDashboard } from "@/features/backoffice/security/components/security-dashboard";
import { SecurityDetailsModal } from "@/features/backoffice/security/components/security-details-modal";
import { SecurityHistoryModal } from "@/features/backoffice/security/components/security-history-modal";
import { SecurityReleaseModal } from "@/features/backoffice/security/components/security-release-modal";
import { useSecurityActions } from "@/features/backoffice/security/hooks/use-security-actions";
import type { SecurityActor, SecurityActorDetail, SecurityBlock, SecurityEvent } from "@/features/backoffice/security/types/security.types";
import { useRouter } from "@/i18n/navigation";

type SecurityView = "dashboard" | "center" | "whitelist";

function resolveView(raw: string | null): SecurityView {
  if (raw === "center" || raw === "whitelist") {
    return raw;
  }
  return "dashboard";
}

export function SecurityPage() {
  const t = useTranslations("backoffice.security");
  const tDashboard = useTranslations("backoffice.dashboard");
  const locale = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();
  const view = resolveView(searchParams.get("view"));
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [releaseTarget, setReleaseTarget] = useState<SecurityBlock | null>(null);
  const [actionTarget, setActionTarget] = useState<SecurityActionTarget>(null);
  const [detailsActor, setDetailsActor] = useState<SecurityActor | null>(null);
  const [detail, setDetail] = useState<SecurityActorDetail | null>(null);
  const [historyActor, setHistoryActor] = useState<SecurityActor | null>(null);
  const [historyEvents, setHistoryEvents] = useState<SecurityEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const summaryQuery = useCallback((token: string) => getSecuritySummary(token), []);
  const timeseriesQuery = useCallback((token: string) => getSecurityTimeseries(token), []);
  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setSearchQuery(searchInput.trim());
    }, 300);
    return () => window.clearTimeout(timeout);
  }, [searchInput]);

  useEffect(() => {
    setPage(1);
  }, [pageSize, searchQuery, view]);

  const actorsQuery = useCallback((token: string) => getSecurityActors(token, { page, page_size: pageSize, q: searchQuery }), [page, pageSize, searchQuery]);
  const whitelistActorsQuery = useCallback((token: string) => getSecurityActors(token, { page, page_size: pageSize, status: "whitelisted", q: searchQuery }), [page, pageSize, searchQuery]);
  const summaryState = useBackofficeQuery(summaryQuery);
  const timeseriesState = useBackofficeQuery(timeseriesQuery);
  const actorsState = useBackofficeQuery(actorsQuery, [page, pageSize, searchQuery]);
  const whitelistState = useBackofficeQuery(whitelistActorsQuery, [page, pageSize, searchQuery]);

  const refreshAll = useCallback(() => {
    void summaryState.refetch();
    void timeseriesState.refetch();
    void actorsState.refetch();
    void whitelistState.refetch();
  }, [actorsState, summaryState, timeseriesState, whitelistState]);

  const actions = useSecurityActions(refreshAll);

  const openDetails = useCallback(async (actor: SecurityActor) => {
    setDetailsActor(actor);
    setDetail(null);
    if (!actorsState.token) {
      return;
    }
    const data = await getSecurityActorDetails(actorsState.token, actor.id);
    setDetail(data);
  }, [actorsState.token]);

  const openDetailsById = useCallback(async (actorId: string) => {
    if (!actorsState.token) {
      return;
    }
    const data = await getSecurityActorDetails(actorsState.token, actorId);
    setDetailsActor(data.actor);
    setDetail(data);
  }, [actorsState.token]);

  const openHistory = useCallback(async (actor: SecurityActor) => {
    setHistoryActor(actor);
    setHistoryLoading(true);
    setHistoryEvents([]);
    try {
      if (!actorsState.token) {
        return;
      }
      const data = await getSecurityActorHistory(actorsState.token, actor.id);
      setHistoryEvents(data.results);
    } finally {
      setHistoryLoading(false);
    }
  }, [actorsState.token]);

  const tabs = useMemo(() => (
    <div className="inline-flex items-center gap-2 rounded-xl border p-1" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
      {(["dashboard", "center", "whitelist"] as SecurityView[]).map((item) => (
        <button
          key={item}
          type="button"
          className="inline-flex h-10 items-center rounded-lg border px-4 text-sm font-semibold transition-colors"
          style={{
            borderColor: view === item ? (item === "dashboard" ? "#16a34a" : item === "whitelist" ? "#ea580c" : "#2563eb") : "var(--border)",
            backgroundColor: view === item ? (item === "dashboard" ? "#16a34a" : item === "whitelist" ? "#ea580c" : "#2563eb") : "var(--surface-2)",
            color: view === item ? "#ffffff" : "var(--text)",
          }}
          onClick={() => router.push(`/backoffice/security?view=${item}`)}
        >
          {t(`tabs.${item}`)}
        </button>
      ))}
    </div>
  ), [router, t, view]);

  const activeActorsState = view === "whitelist" ? whitelistState : actorsState;
  const pagesCount = Math.max(1, Math.ceil((activeActorsState.data?.count ?? 0) / pageSize));
  const pageTitle = view === "dashboard" ? tDashboard("title") : view === "whitelist" ? t("tabs.whitelist") : t("title");

  return (
    <section className="min-w-0">
      <PageHeader
        title={pageTitle}
        description={t("subtitle")}
        switcher={tabs}
        actions={(
          <button
            type="button"
            className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => {
              refreshAll();
            }}
          >
            <RefreshCw size={16} className="animate-spin" style={{ animationDuration: "2.2s" }} />
            {tDashboard("actions.refreshOperationalContour")}
          </button>
        )}
      />
      {view !== "dashboard" ? (
        <section className="mb-3 flex items-center gap-2">
          <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto px-1 py-1">
            <input
              type="text"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder={t("filters.searchPlaceholder")}
              className="h-10 w-[220px] xl:w-[280px] rounded-md border px-3 text-sm shrink-0"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            />
            <select
              value={String(pageSize)}
              onChange={(event) => setPageSize(Number(event.target.value))}
              className="h-10 rounded-md border px-3 text-sm shrink-0"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            >
              {[15, 25, 50, 100].map((size) => (
                <option key={size} value={size}>
                  {`${t("pagination.perPage")}: ${size}`}
                </option>
              ))}
            </select>
          </div>
        </section>
      ) : null}
      {view === "dashboard" ? (
        <SecurityDashboard
          summary={summaryState.data}
          timeseries={timeseriesState.data}
          isLoading={summaryState.isLoading || timeseriesState.isLoading}
          error={summaryState.error || timeseriesState.error}
          t={t}
          onRelease={setReleaseTarget}
          onOpenActorById={openDetailsById}
        />
      ) : view === "center" ? (
        <SecurityCenterTable
          rows={actorsState.data?.results ?? []}
          totalCount={actorsState.data?.count ?? 0}
          page={page}
          pagesCount={pagesCount}
          isLoading={actorsState.isLoading}
          error={actorsState.error}
          t={t}
          onPageChange={setPage}
          onOpenDetails={openDetails}
          onOpenHistory={openHistory}
          onRelease={setReleaseTarget}
          onWhitelist={(actor) => setActionTarget({ kind: "whitelist", actor })}
          onExtend={(actor) => setActionTarget({ kind: "extend", actor })}
          onCopy={actions.copyIp}
          onComment={(actor) => setActionTarget({ kind: "comment", actor })}
          onFalsePositive={(actor) => setActionTarget({ kind: "falsePositive", actor })}
          onReblock={(actor) => setActionTarget({ kind: "reblock", actor })}
        />
      ) : (
        <SecurityCenterTable
          rows={whitelistState.data?.results ?? []}
          totalCount={whitelistState.data?.count ?? 0}
          page={page}
          pagesCount={pagesCount}
          isLoading={whitelistState.isLoading}
          error={whitelistState.error}
          t={t}
          onPageChange={setPage}
          onOpenDetails={openDetails}
          onOpenHistory={openHistory}
          onRelease={setReleaseTarget}
          onWhitelist={(actor) => setActionTarget({ kind: "whitelist", actor })}
          onExtend={(actor) => setActionTarget({ kind: "extend", actor })}
          onCopy={actions.copyIp}
          onComment={(actor) => setActionTarget({ kind: "comment", actor })}
          onFalsePositive={(actor) => setActionTarget({ kind: "falsePositive", actor })}
          onReblock={(actor) => setActionTarget({ kind: "reblock", actor })}
        />
      )}

      <SecurityDetailsModal
        actor={detailsActor}
        detail={detail}
        locale={locale}
        t={t}
        onClose={() => setDetailsActor(null)}
        onHistory={openHistory}
        onRelease={setReleaseTarget}
        onReblock={(actor) => setActionTarget({ kind: "reblock", actor })}
        onWhitelist={(actor) => setActionTarget({ kind: "whitelist", actor })}
      />
      <SecurityHistoryModal actor={historyActor} events={historyEvents} isLoading={historyLoading} locale={locale} t={t} onClose={() => setHistoryActor(null)} />
      <SecurityReleaseModal
        block={releaseTarget}
        t={t}
        isSubmitting={actions.submitting}
        onClose={() => setReleaseTarget(null)}
        onConfirm={(reason) => {
          if (releaseTarget) {
            void actions.release(releaseTarget, reason);
            setReleaseTarget(null);
          }
        }}
      />
      <SecurityActionModal
        target={actionTarget}
        t={t}
        isSubmitting={actions.submitting}
        onClose={() => setActionTarget(null)}
        onConfirm={({ reason, minutes }) => {
          if (!actionTarget) {
            return;
          }
          if (actionTarget.kind === "whitelist") {
            void actions.whitelist(actionTarget.actor, reason);
          } else if (actionTarget.kind === "extend") {
            void actions.extend(actionTarget.actor, minutes, reason);
          } else if (actionTarget.kind === "comment") {
            void actions.comment(actionTarget.actor, reason);
          } else if (actionTarget.kind === "falsePositive") {
            void actions.falsePositive(actionTarget.actor, reason);
          } else {
            void actions.reblock(actionTarget.actor, reason);
          }
          setActionTarget(null);
        }}
      />
    </section>
  );
}
