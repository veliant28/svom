"use client";

import { X } from "lucide-react";
import { useCallback } from "react";
import { useTranslations } from "next-intl";

import { getAutoDbMatchingJob } from "@/features/backoffice/api/backoffice-api";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { AutoDbEvidence, AutoDbJobDetail } from "@/features/backoffice/types/backoffice";

import { formatDateTime, StatusPill, surfaceStyle } from "./ui";

export function AutoDbEvidenceDrawer({ jobId, onClose }: { jobId: string | null; onClose: () => void }) {
  const t = useTranslations("backoffice.autodbMatching");
  const queryFn = useCallback((token: string) => jobId ? getAutoDbMatchingJob(token, jobId) : Promise.resolve(null), [jobId]);
  const { data, isLoading, error } = useBackofficeQuery<AutoDbJobDetail | null>(queryFn, [jobId]);

  if (!jobId) {
    return null;
  }

  return (
    <aside className="fixed inset-y-0 right-0 z-40 w-full max-w-xl border-l p-4 shadow-2xl" style={{ ...surfaceStyle, backgroundColor: "var(--surface)" }}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold">{t("drawer.title")}</h2>
        <button type="button" className="rounded-md border p-2" style={surfaceStyle} onClick={onClose} aria-label={t("actions.close")}>
          <X size={16} />
        </button>
      </div>
      <AsyncState isLoading={isLoading} error={error} empty={!data} emptyLabel={t("states.empty")}>
        <div className="grid max-h-[calc(100vh-72px)] gap-3 overflow-y-auto pr-1">
          <Section title={t("drawer.productInfo")} data={data?.drawer.product_info ?? {}} />
          <Section title={t("drawer.brandResolution")} data={data?.drawer.brand_resolution ?? {}} />
          <Section title={t("drawer.articleSource")} data={data?.drawer.article_source ?? {}} />
          <Evidence title={t("drawer.localEvidence")} evidence={data?.drawer.local_lookup_evidence} />
          <Evidence title={t("drawer.remoteEvidence")} evidence={data?.drawer.remote_lookup_evidence} />
          <Evidence title={t("drawer.cloneSync")} evidence={data?.drawer.clone_sync_state} />
          <Evidence title={t("drawer.linkAudit")} evidence={data?.drawer.link_audit_result} />
          <Section title={t("drawer.enrichment")} data={data?.drawer.enrichment_availability ?? {}} />
          <div className="grid gap-2">
            <h3 className="text-sm font-semibold">{t("drawer.evidenceHistory")}</h3>
            {(data?.drawer.evidence ?? []).map((item) => (
              <Evidence key={item.id} title={`${item.stage || "-"} / ${formatDateTime(item.created_at)}`} evidence={item} />
            ))}
          </div>
        </div>
      </AsyncState>
    </aside>
  );
}

function Section({ title, data }: { title: string; data: Record<string, unknown> }) {
  return (
    <section className="rounded-xl border p-3" style={surfaceStyle}>
      <h3 className="mb-2 text-sm font-semibold">{title}</h3>
      <dl className="grid gap-1 text-xs">
        {Object.entries(data).map(([key, value]) => (
          <div key={key} className="grid grid-cols-[140px_minmax(0,1fr)] gap-2">
            <dt style={{ color: "var(--muted)" }}>{key}</dt>
            <dd className="min-w-0 break-words font-medium">{String(value ?? "-")}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Evidence({ title, evidence }: { title: string; evidence?: AutoDbEvidence }) {
  if (!evidence || !Object.keys(evidence).length) {
    return <Section title={title} data={{ status: "-" }} />;
  }
  return (
    <section className="rounded-xl border p-3" style={surfaceStyle}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        <StatusPill tone={evidence.result === "safe_link_candidate" ? "ok" : evidence.result === "quota_paused" ? "danger" : "neutral"}>
          {evidence.result || "-"}
        </StatusPill>
      </div>
      <dl className="grid gap-1 text-xs">
        {["source", "supplier_id", "article_value", "canonical_article", "remote_stored_article", "article_prd_present", "prd_present", "reason"].map((key) => (
          <div key={key} className="grid grid-cols-[140px_minmax(0,1fr)] gap-2">
            <dt style={{ color: "var(--muted)" }}>{key}</dt>
            <dd className="min-w-0 break-words font-medium">{String(evidence[key as keyof AutoDbEvidence] ?? "-")}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
