"use client";

import type { FormEvent } from "react";
import { useCallback, useEffect, useState } from "react";

import { getAdminSettings, getCommissionsSummary, listAdminCommissions, updateAdminSettings } from "@/lib/api/admin";
import type { AdminCommission, CommissionSummary, PlatformSettings } from "@/types/admin";

function formatPrice(n: number, currency = "KZT") {
  return `${new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n)} ${currency}`;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "2-digit", month: "short", year: "numeric" });
}

function SummaryCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: "20px 24px" }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 10 }}>
        {label}
      </div>
      <div style={{ fontSize: 30, fontWeight: 800, color: color ?? "#0f172a", lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 13, color: "#94a3b8", marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

export default function AdminCommissionsPage() {
  const [items, setItems] = useState<AdminCommission[]>([]);
  const [summary, setSummary] = useState<CommissionSummary | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const SIZE = 50;

  // Settings state
  const [settings, setSettings] = useState<PlatformSettings | null>(null);
  const [rateInput, setRateInput] = useState("");
  const [savingRate, setSavingRate] = useState(false);
  const [rateError, setRateError] = useState<string | null>(null);
  const [rateSaved, setRateSaved] = useState(false);

  const load = useCallback(() => {
    setIsLoading(true);
    Promise.all([
      listAdminCommissions(page, SIZE),
      page === 1 ? getCommissionsSummary() : Promise.resolve(summary),
    ])
      .then(([res, sum]) => {
        setItems(res.items);
        setTotal(res.total);
        if (sum) setSummary(sum);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    getAdminSettings()
      .then((s) => { setSettings(s); setRateInput(String(Number(s.commission_rate) * 100)); })
      .catch(() => {});
  }, []);

  async function handleSaveRate(e: FormEvent) {
    e.preventDefault();
    setRateError(null);
    setRateSaved(false);
    const num = parseFloat(rateInput.replace(",", "."));
    if (isNaN(num) || num < 0 || num > 100) {
      setRateError("Введите число от 0 до 100");
      return;
    }
    setSavingRate(true);
    try {
      const updated = await updateAdminSettings({ commission_rate: (num / 100).toFixed(4) });
      setSettings(updated);
      setRateInput(String(Number(updated.commission_rate) * 100));
      setRateSaved(true);
      setTimeout(() => setRateSaved(false), 3000);
    } catch (e: unknown) {
      setRateError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setSavingRate(false);
    }
  }

  const pages = Math.ceil(total / SIZE) || 1;

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28, gap: 24, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: "#0f172a" }}>Комиссии</h1>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>
            Комиссия Novex по оплаченным заказам
          </p>
        </div>

        {/* Commission rate editor */}
        <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: "18px 22px", minWidth: 280 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 12 }}>
            Ставка комиссии
          </div>
          <form onSubmit={(e) => void handleSaveRate(e)} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", border: "1px solid #e5e7eb", borderRadius: 10, overflow: "hidden", background: "#f8fafc" }}>
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  value={rateInput}
                  onChange={(e) => { setRateInput(e.target.value); setRateError(null); setRateSaved(false); }}
                  style={{ flex: 1, border: "none", background: "transparent", padding: "9px 12px", fontSize: 15, fontWeight: 700, color: "#0f172a", outline: "none", fontFamily: "inherit", width: 80 }}
                />
                <span style={{ padding: "9px 12px 9px 0", fontSize: 15, fontWeight: 700, color: "#64748b" }}>%</span>
              </div>
              {rateError && <div style={{ fontSize: 12, color: "#dc2626", marginTop: 4 }}>{rateError}</div>}
              {rateSaved && <div style={{ fontSize: 12, color: "#16a34a", marginTop: 4 }}>Сохранено</div>}
            </div>
            <button
              type="submit"
              disabled={savingRate}
              style={{ padding: "9px 18px", borderRadius: 10, border: "none", background: "#0f172a", color: "#fff", fontSize: 13, fontWeight: 600, cursor: savingRate ? "not-allowed" : "pointer", opacity: savingRate ? 0.6 : 1, whiteSpace: "nowrap", fontFamily: "inherit" }}
            >
              {savingRate ? "…" : "Сохранить"}
            </button>
          </form>
          {settings && (
            <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 8 }}>
              Текущая ставка: {(Number(settings.commission_rate) * 100).toFixed(2)}% от суммы заказа
            </div>
          )}
        </div>
      </div>

      {error && (
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 10, padding: "12px 16px", color: "#b91c1c", fontSize: 14, marginBottom: 20 }}>
          {error}
        </div>
      )}

      {/* Summary cards */}
      {summary && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 28 }}>
          <SummaryCard
            label="Общий оборот"
            value={formatPrice(summary.total_gross, summary.currency)}
            sub="сумма заказов"
          />
          <SummaryCard
            label="Комиссия Novex"
            value={formatPrice(summary.total_commission, summary.currency)}
            sub={settings ? `${(Number(settings.commission_rate) * 100).toFixed(2)}% от оборота` : "от оборота"}
            color="#16a34a"
          />
          <SummaryCard
            label="Транзакций"
            value={String(summary.count)}
            sub="оплаченных заказов"
          />
        </div>
      )}

      {/* Table */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "80px 100px 140px 160px 160px 120px", gap: 12, padding: "12px 24px", background: "#f8fafc", borderBottom: "1px solid #e5e7eb", fontSize: 12, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          <span>ID</span>
          <span>Заказ</span>
          <span>Перевозчик</span>
          <span>Сумма заказа</span>
          <span>Комиссия</span>
          <span>Дата</span>
        </div>

        {isLoading ? (
          <div style={{ padding: 48, textAlign: "center", color: "#64748b", fontSize: 14 }}>Загружаем…</div>
        ) : items.length === 0 ? (
          <div style={{ padding: "48px 24px", textAlign: "center", color: "#64748b", fontSize: 14 }}>
            Записей пока нет — они появятся после первой оплаты
          </div>
        ) : (
          items.map((c, idx) => (
            <div
              key={c.id}
              style={{ display: "grid", gridTemplateColumns: "80px 100px 140px 160px 160px 120px", gap: 12, padding: "14px 24px", borderBottom: idx === items.length - 1 ? "none" : "1px solid #f1f5f9", alignItems: "center" }}
            >
              <span style={{ fontFamily: "monospace", fontSize: 12, color: "#94a3b8" }}>#{c.id}</span>
              <span style={{ fontFamily: "monospace", fontSize: 13, color: "#475569", fontWeight: 600 }}>#{c.order_draft_id}</span>
              <span style={{ fontSize: 13, color: "#0f172a", fontWeight: 500 }}>{c.carrier_code}</span>
              <span style={{ fontSize: 13, color: "#475569" }}>{formatPrice(c.gross_amount, c.currency)}</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: "#16a34a" }}>
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

      {/* Pagination */}
      {pages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 20 }}>
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid #e5e7eb", background: "#fff", color: "#475569", fontSize: 13, fontWeight: 500, cursor: page === 1 ? "not-allowed" : "pointer", opacity: page === 1 ? 0.4 : 1, fontFamily: "inherit" }}
          >
            ← Назад
          </button>
          <span style={{ padding: "7px 16px", fontSize: 13, color: "#64748b" }}>
            {page} / {pages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page === pages}
            style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid #e5e7eb", background: "#fff", color: "#475569", fontSize: 13, fontWeight: 500, cursor: page === pages ? "not-allowed" : "pointer", opacity: page === pages ? 0.4 : 1, fontFamily: "inherit" }}
          >
            Вперёд →
          </button>
        </div>
      )}
    </>
  );
}
