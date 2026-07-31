"use client";

import { useCallback, useEffect, useState } from "react";

import {
  getCarrierCommissionsSummary,
  listCarrierCommissions,
  type CarrierCommission,
} from "@/lib/api/carrier";
import type { CommissionSummary } from "@/types/admin";

function formatPrice(n: number, currency = "KZT") {
  return `${new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: "auto" }).format(n)} ${currency}`;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "2-digit", month: "short", year: "numeric" });
}

// 7 столбцов: ID · Заказ · Номер заказа · Штрих-код · ID Novex ·
// К выплате · Дата. Оборот и комиссия скрыты — это внутренние цифры Novex.
const TABLE_COLS = "60px 80px 160px 140px 200px 150px 120px";

function IdCell({ value }: { value: string | null }) {
  if (!value) return <span style={{ fontSize: 12, color: "#cbd5e1" }}>-</span>;
  return (
    <span
      title={value}
      style={{
        fontFamily: "monospace",
        fontSize: 12,
        color: "#334155",
        whiteSpace: "nowrap",
        overflow: "hidden",
        textOverflow: "ellipsis",
      }}
    >
      {value}
    </span>
  );
}

function InfoDot({ tooltip, color = "#94a3b8" }: { tooltip: string; color?: string }) {
  return (
    <span
      title={tooltip}
      aria-label={tooltip}
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: 14, height: 14, borderRadius: "50%",
        border: `1.5px solid ${color}`, color,
        fontSize: 10, fontWeight: 700, fontFamily: "serif",
        cursor: "help", lineHeight: 1,
      }}
    >
      i
    </span>
  );
}

function SummaryCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: "20px 24px", flex: 1, minWidth: 220 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 800, color: color ?? "#0f172a", lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

export default function CarrierCommissionsPage() {
  const [items, setItems] = useState<CarrierCommission[]>([]);
  const [summary, setSummary] = useState<CommissionSummary | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const SIZE = 50;

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      listCarrierCommissions(page, SIZE),
      page === 1 ? getCarrierCommissionsSummary() : Promise.resolve(summary),
    ])
      .then(([res, sum]) => {
        setItems(res.items);
        setTotal(res.total);
        if (sum) setSummary(sum);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  useEffect(() => { load(); }, [load]);

  const pages = Math.ceil(total / SIZE) || 1;

  return (
    <>
      {/* ── Summary cards ─────────────────────────────────────── */}
      <div style={{ display: "flex", gap: 16, alignItems: "stretch", marginBottom: 20, flexWrap: "wrap" }}>
        {summary ? (
          <>
            <SummaryCard
              label="Ваша выручка"
              value={formatPrice(summary.total_carrier_payout, summary.currency)}
              sub="к перечислению"
              color="#0369a1"
            />
            <SummaryCard
              label="Оплачено заказов"
              value={String(summary.count)}
              sub="учтено в выручке"
            />
          </>
        ) : (
          <>
            {[0, 1].map(i => (
              <div key={i} style={{ flex: 1, background: "#f8fafc", border: "1px solid #e5e7eb", borderRadius: 14, padding: "20px 24px", minHeight: 80, minWidth: 220 }} />
            ))}
          </>
        )}
      </div>

      {/* ── Error ─────────────────────────────────────────────── */}
      {error && (
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 10, padding: "12px 16px", color: "#b91c1c", fontSize: 14, marginBottom: 20 }}>
          {error}
        </div>
      )}

      {/* ── History table ─────────────────────────────────────── */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "auto" }}>
        <div style={{ minWidth: 940 }}>
          <div style={{ display: "grid", gridTemplateColumns: TABLE_COLS, gap: 12, padding: "12px 24px", background: "#f8fafc", borderBottom: "1px solid #e5e7eb", fontSize: 12, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            <span>ID</span>
            <span>Заказ</span>
            <span>Номер заказа</span>
            <span>Штрих-код</span>
            <span>ID Novex</span>
            <span>К выплате</span>
            <span>Дата</span>
          </div>

          {loading ? (
            <div style={{ padding: 48, textAlign: "center", color: "#64748b", fontSize: 14 }}>Загружаем…</div>
          ) : items.length === 0 ? (
            <div style={{ padding: "48px 24px", textAlign: "center", color: "#64748b", fontSize: 14 }}>
              Записей пока нет - появятся после первой оплаты
            </div>
          ) : (
            items.map((c, idx) => {
              const isReversal = c.status === "reversal";
              const isReversed = c.status === "reversed";
              const rowBg = isReversal ? "#fef2f2" : isReversed ? "#fafafa" : "transparent";
              const strike = isReversed ? "line-through" : "none";
              const dim = isReversed ? 0.6 : 1;
              const payoutColor = isReversal ? "#dc2626" : "#0369a1";
              const iconTooltip = isReversal
                ? `Возврат по отменённому заказу${c.reversal_reason ? `: ${c.reversal_reason}` : ""}`
                : isReversed
                  ? `Начисление отменено${c.reversal_reason ? `: ${c.reversal_reason}` : ""}`
                  : "";
              return (
                <div
                  key={c.id}
                  style={{ display: "grid", gridTemplateColumns: TABLE_COLS, gap: 12, padding: "14px 24px", borderBottom: idx === items.length - 1 ? "none" : "1px solid #f1f5f9", alignItems: "center", background: rowBg }}
                >
                  <span style={{ fontFamily: "monospace", fontSize: 12, color: "#94a3b8" }}>#{c.id}</span>
                  <span style={{ fontFamily: "monospace", fontSize: 13, color: "#475569", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 6 }}>
                    #{c.order_draft_id}
                    {(isReversal || isReversed) && (
                      <InfoDot color={isReversal ? "#dc2626" : "#94a3b8"} tooltip={iconTooltip} />
                    )}
                  </span>
                  <IdCell value={c.carrier_tracking_number} />
                  <IdCell value={c.carrier_barcode} />
                  <IdCell value={c.tracking_number} />
                  <span style={{ fontSize: 13, fontWeight: 700, color: payoutColor, textDecoration: strike, opacity: dim }}>
                    {/* Для старых записей carrier_payout мог не проставиться —
                       используем тот же fallback, что и backend в summary:
                       gross_amount − commission_amount. */}
                    {formatPrice(
                      c.carrier_payout != null
                        ? Number(c.carrier_payout)
                        : Number(c.gross_amount) - Number(c.commission_amount),
                      c.currency,
                    )}
                  </span>
                  <span style={{ fontSize: 12, color: "#94a3b8" }}>{formatDate(c.created_at)}</span>
                </div>
              );
            })
          )}
        </div>
      </div>

      {pages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 20 }}>
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
            style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid #e5e7eb", background: "#fff", color: "#475569", fontSize: 13, fontWeight: 500, cursor: page === 1 ? "not-allowed" : "pointer", opacity: page === 1 ? 0.4 : 1, fontFamily: "inherit" }}
          >← Назад</button>
          <span style={{ padding: "7px 16px", fontSize: 13, color: "#64748b" }}>{page} / {pages}</span>
          <button
            onClick={() => setPage((p) => Math.min(pages, p + 1))} disabled={page === pages}
            style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid #e5e7eb", background: "#fff", color: "#475569", fontSize: 13, fontWeight: 500, cursor: page === pages ? "not-allowed" : "pointer", opacity: page === pages ? 0.4 : 1, fontFamily: "inherit" }}
          >Вперёд →</button>
        </div>
      )}
    </>
  );
}
