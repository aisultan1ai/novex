"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { intlLocale } from "@/i18n/runtime";

import {
  adminApproveCancellation,
  adminListCancellations,
  adminRejectCancellation,
  adminRetryApiCancellation,
  type CancellationRequestFull,
  type CancellationStatus,
} from "@/lib/api/cancellations";
import { useIsMobile } from "@/hooks/use-is-mobile";
import { errorMessage } from "@/lib/api/client";
import { Link } from "@/i18n/navigation";

const FILTERS: { value: CancellationStatus | ""; label: string }[] = [
  // label - ключ admin.cancellations.filters.<label>
  { value: "pending", label: "pending" },
  { value: "", label: "all" },
  { value: "api_cancelled", label: "api_cancelled" },
  { value: "approved", label: "approved" },
  { value: "rejected", label: "rejected" },
];

// Quiet palette: only "pending" stands out (navy), the rest are muted.
const STATUS_VIEW: Record<CancellationStatus, { label: string; bg: string; fg: string }> = {
  // label - ключ admin.cancellations.status.<label>
  pending:       { label: "pending",       bg: "#E2E8EE", fg: "#0B2545" },
  api_cancelled: { label: "api_cancelled", bg: "#F1F5F9", fg: "#64748b" },
  approved:      { label: "approved",      bg: "#F1F5F9", fg: "#64748b" },
  rejected:      { label: "rejected",      bg: "#F1F5F9", fg: "#64748b" },
};

// Carriers with a cancel API — only for these «Повторить через API» makes sense.
const API_CANCEL_CARRIERS = new Set(["cse", "exline"]);

const SIZE = 20;

export default function AdminCancellationsPage() {
  const isMobile = useIsMobile();
  const t = useTranslations("admin.cancellations");
  const [filter, setFilter] = useState<CancellationStatus | "">("pending");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<CancellationRequestFull[]>([]);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    adminListCancellations({ status: filter || undefined, page, size: SIZE })
      .then((r) => { setItems(r.items); setPages(r.pages); setTotal(r.total); setError(null); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filter, page]);

  useEffect(() => { load(); }, [load]);

  return (
    <>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0B2545" }}>{t("title")}</h2>
        <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>
          {t("subtitle", { n: total })}
        </p>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {FILTERS.map((f) => {
          const active = f.value === filter;
          return (
            <button
              key={f.label}
              onClick={() => { setFilter(f.value); setPage(1); }}
              style={{
                padding: "7px 14px", borderRadius: 999, fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
                border: `1px solid ${active ? "#0B2545" : "#E2E8EE"}`,
                background: active ? "#0B2545" : "#fff",
                color: active ? "#fff" : "#475569",
              }}
            >
              {t(`filters.${f.label}`)}
            </button>
          );
        })}
      </div>

      {error && (
        <div style={{ padding: "10px 14px", borderRadius: 10, background: "#fef2f2", color: "#b91c1c", fontSize: 13, marginBottom: 12 }}>{error}</div>
      )}

      {loading ? (
        <div style={{ color: "#64748b", fontSize: 14, padding: 20 }}>{t("loading")}</div>
      ) : items.length === 0 ? (
        <div style={{ padding: "40px 20px", textAlign: "center", color: "#94a3b8", fontSize: 14, background: "#fff", border: "1px solid #E2E8EE", borderRadius: 14 }}>
          {filter === "pending" ? t("emptyPending") : t("empty")}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {items.map((req) => (
            <CancellationCard key={req.id} req={req} isMobile={isMobile} onChanged={load} />
          ))}
        </div>
      )}

      {pages > 1 && (
        <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 16 }}>
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} style={pagerBtn}>←</button>
          <span style={{ fontSize: 13, color: "#64748b", alignSelf: "center" }}>{page} / {pages}</span>
          <button onClick={() => setPage((p) => Math.min(pages, p + 1))} disabled={page === pages} style={pagerBtn}>→</button>
        </div>
      )}
    </>
  );
}

function CancellationCard({ req, isMobile, onChanged }: { req: CancellationRequestFull; isMobile: boolean; onChanged: () => void }) {
  const t = useTranslations("admin.cancellations");
  const [busy, setBusy] = useState<"approve" | "reject" | "retry" | null>(null);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [comment, setComment] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const view = STATUS_VIEW[req.status];
  const pending = req.status === "pending";

  async function run(kind: "approve" | "reject" | "retry", fn: () => Promise<unknown>) {
    setBusy(kind);
    setMsg(null);
    try {
      await fn();
      onChanged();
    } catch (e) {
      setMsg(errorMessage(e, t("error")));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, padding: isMobile ? 16 : "18px 22px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap", alignItems: "center", marginBottom: 8 }}>
        <Link href={`/dashboard/admin/orders?order=${req.order_draft_id}`} style={{ fontSize: 15, fontWeight: 800, color: "#0B2545", textDecoration: "none" }}>
          {t("order", { id: req.order_draft_id })}
        </Link>
        <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: view.bg, color: view.fg }}>{t(`status.${view.label}`)}</span>
      </div>
      <div style={{ fontSize: 12, color: "#64748b", marginBottom: 8 }}>
        {req.carrier_code.toUpperCase()} · {new Date(req.created_at).toLocaleString(intlLocale())}
      </div>
      <div style={{ fontSize: 14, color: "#0E1826", marginBottom: 8, lineHeight: 1.5 }}>
        <b>{t("reason")}</b> {req.reason}
      </div>
      {req.api_attempted && req.api_error && (
        <div style={{ padding: "8px 12px", borderRadius: 8, background: "#F8FAFC", border: "1px solid #E2E8EE", color: "#475569", fontSize: 12, marginBottom: 8, wordBreak: "break-word" }}>
          <b>{t("apiFailed")}</b> <span style={{ fontFamily: "monospace" }}>{req.api_error}</span>
        </div>
      )}
      {req.carrier_response && (
        <div style={{ fontSize: 13, color: "#475569", marginBottom: 8 }}><b>{t("response")}</b> {req.carrier_response}</div>
      )}
      {msg && (
        <div style={{ padding: "7px 12px", borderRadius: 8, background: "#F8FAFC", border: "1px solid #E2E8EE", color: "#B91C1C", fontSize: 12, marginBottom: 8 }}>{msg}</div>
      )}

      {pending && !rejectOpen && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4 }}>
          <button
            disabled={busy !== null}
            onClick={() => {
              if (!window.confirm(t("approveConfirm"))) return;
              void run("approve", () => adminApproveCancellation(req.id));
            }}
            style={{ ...actionBtn, background: "#0B2545", color: "#fff", border: "none" }}
          >
            {busy === "approve" ? t("approving") : t("approve")}
          </button>
          {API_CANCEL_CARRIERS.has(req.carrier_code) && (
            <button disabled={busy !== null} onClick={() => void run("retry", () => adminRetryApiCancellation(req.id))} style={actionBtn}>
              {busy === "retry" ? t("sending") : t("retryApi")}
            </button>
          )}
          <button disabled={busy !== null} onClick={() => setRejectOpen(true)} style={actionBtn}>
            {t("reject")}
          </button>
        </div>
      )}

      {pending && rejectOpen && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 4 }}>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder={t("rejectPlaceholder")}
            rows={2}
            style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #E2E8EE", fontSize: 13, fontFamily: "inherit", resize: "vertical" }}
          />
          <div style={{ display: "flex", gap: 8 }}>
            <button
              disabled={busy !== null || comment.trim().length < 3}
              onClick={() => void run("reject", () => adminRejectCancellation(req.id, comment.trim()))}
              style={{ ...actionBtn, background: "#0B2545", color: "#fff", border: "none", opacity: comment.trim().length < 3 ? 0.5 : 1 }}
            >
              {busy === "reject" ? t("rejecting") : t("rejectSubmit")}
            </button>
            <button onClick={() => { setRejectOpen(false); setComment(""); }} style={actionBtn}>{t("back")}</button>
          </div>
        </div>
      )}
    </div>
  );
}

const actionBtn: React.CSSProperties = {
  padding: "8px 14px", borderRadius: 8, border: "1px solid #E2E8EE", background: "#fff",
  color: "#0B2545", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
};

const pagerBtn: React.CSSProperties = {
  padding: "6px 12px", borderRadius: 8, border: "1px solid #E2E8EE", background: "#fff", cursor: "pointer", fontFamily: "inherit",
};
