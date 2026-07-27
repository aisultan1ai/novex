"use client";

import { useCallback, useEffect, useState } from "react";

import {
  getCarrierCommissionsSummary,
  getCarrierCommissionConfig,
  listCarrierCommissions,
  type CarrierCommissionConfig,
} from "@/lib/api/carrier";
import type { AdminCommission, CommissionSummary } from "@/types/admin";

const TYPE_LABELS: Record<string, string> = {
  percentage: "Процент",
  fixed:      "Фиксированная",
  combined:   "Комбинированная",
};

function formatPrice(n: number, currency = "KZT") {
  return `${new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n)} ${currency}`;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "2-digit", month: "short", year: "numeric" });
}

function formatRate(config: CarrierCommissionConfig): string {
  if (!config.is_set) return "не установлена — используется глобальная ставка платформы";
  const parts: string[] = [];
  if (config.commission_rate) parts.push(`${(Number(config.commission_rate) * 100).toFixed(2)}%`);
  if (config.fixed_amount) parts.push(`${config.fixed_amount} ${config.currency}`);
  const label = config.commission_type ? TYPE_LABELS[config.commission_type] ?? config.commission_type : "";
  return `${label ? label + ": " : ""}${parts.join(" + ")}`;
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
  const [items, setItems] = useState<AdminCommission[]>([]);
  const [summary, setSummary] = useState<CommissionSummary | null>(null);
  const [config, setConfig] = useState<CarrierCommissionConfig | null>(null);
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
      page === 1 ? getCarrierCommissionConfig() : Promise.resolve(config),
    ])
      .then(([res, sum, cfg]) => {
        setItems(res.items);
        setTotal(res.total);
        if (sum) setSummary(sum);
        if (cfg) setConfig(cfg);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  useEffect(() => { load(); }, [load]);

  const pages = Math.ceil(total / SIZE) || 1;

  return (
    <>
      {/* ── Read-only rate card ─────────────────────────────────── */}
      <div style={{
        background: "#fff",
        border: "1px solid #e5e7eb",
        borderRadius: 14,
        padding: "18px 24px",
        marginBottom: 16,
        display: "flex",
        alignItems: "center",
        gap: 16,
        flexWrap: "wrap",
      }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10,
          background: "#eef2ff",
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4338ca" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
          </svg>
        </div>
        <div style={{ flex: 1, minWidth: 220 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
            Ваша ставка комиссии
          </div>
          <div style={{ fontSize: 15, fontWeight: 600, color: "#0f172a" }}>
            {config ? formatRate(config) : "Загружаем…"}
          </div>
          <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>
            Устанавливается администратором платформы
          </div>
        </div>
      </div>

      {/* ── Summary cards ─────────────────────────────────────── */}
      <div style={{ display: "flex", gap: 16, alignItems: "stretch", marginBottom: 20, flexWrap: "wrap" }}>
        {summary ? (
          <>
            <SummaryCard
              label="Оборот по вашим заказам"
              value={formatPrice(summary.total_gross, summary.currency)}
              sub={`${summary.count} оплаченных заказов`}
            />
            <SummaryCard
              label="Ваша выручка"
              value={formatPrice(summary.total_carrier_payout, summary.currency)}
              sub="к перечислению"
              color="#0369a1"
            />
            <SummaryCard
              label="Комиссия платформы"
              value={formatPrice(summary.total_commission, summary.currency)}
              sub={
                summary.total_gross > 0
                  ? `${((summary.total_commission / summary.total_gross) * 100).toFixed(2)}% от оборота`
                  : "удержано"
              }
              color="#16a34a"
            />
          </>
        ) : (
          <>
            {[0,1,2].map(i => (
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
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "80px 100px 160px 160px 160px 120px", gap: 12, padding: "12px 24px", background: "#f8fafc", borderBottom: "1px solid #e5e7eb", fontSize: 12, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          <span>ID</span><span>Заказ</span><span>Сумма заказа</span><span>К выплате</span><span>Комиссия</span><span>Дата</span>
        </div>

        {loading ? (
          <div style={{ padding: 48, textAlign: "center", color: "#64748b", fontSize: 14 }}>Загружаем…</div>
        ) : items.length === 0 ? (
          <div style={{ padding: "48px 24px", textAlign: "center", color: "#64748b", fontSize: 14 }}>
            Записей пока нет — появятся после первой оплаты
          </div>
        ) : (
          items.map((c, idx) => (
            <div
              key={c.id}
              style={{ display: "grid", gridTemplateColumns: "80px 100px 160px 160px 160px 120px", gap: 12, padding: "14px 24px", borderBottom: idx === items.length - 1 ? "none" : "1px solid #f1f5f9", alignItems: "center" }}
            >
              <span style={{ fontFamily: "monospace", fontSize: 12, color: "#94a3b8" }}>#{c.id}</span>
              <span style={{ fontFamily: "monospace", fontSize: 13, color: "#475569", fontWeight: 600 }}>#{c.order_draft_id}</span>
              <span style={{ fontSize: 13, color: "#475569" }}>{formatPrice(c.gross_amount, c.currency)}</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: "#0369a1" }}>
                {c.carrier_payout != null ? formatPrice(c.carrier_payout, c.currency) : "—"}
              </span>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#64748b" }}>
                {formatPrice(c.commission_amount, c.currency)}
                <span style={{ fontSize: 11, color: "#94a3b8", fontWeight: 400, marginLeft: 6 }}>
                  ({(Number(c.commission_rate) * 100).toFixed(0)}%)
                </span>
              </span>
              <span style={{ fontSize: 12, color: "#94a3b8" }}>{formatDate(c.created_at)}</span>
            </div>
          ))
        )}
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
