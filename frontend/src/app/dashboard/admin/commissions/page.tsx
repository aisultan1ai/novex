"use client";

import type { FormEvent } from "react";
import { useCallback, useEffect, useState } from "react";

import { getAdminSettings, getCommissionsSummary, listAdminCommissions, updateAdminSettings } from "@/lib/api/admin";
import {
  deleteCommissionConfig,
  listCommissionConfigs,
  upsertCommissionConfig,
  type CommissionConfigResponse,
  type CommissionConfigUpsert,
  type CommissionType,
} from "@/lib/api/commission_configs";
import type { AdminCommission, CommissionSummary, PlatformSettings } from "@/types/admin";

const TYPE_LABELS: Record<CommissionType, string> = {
  percentage: "Процент",
  fixed:      "Фиксированная",
  combined:   "Комбинированная",
};

const EMPTY_FORM: CommissionConfigUpsert & { carrier_code: string } = {
  carrier_code:    "",
  commission_type: "percentage",
  commission_rate: null,
  fixed_amount:    null,
  currency:        "KZT",
};

function typeNeedsRate(t: CommissionType) { return t === "percentage" || t === "combined"; }
function typeNeedsFixed(t: CommissionType) { return t === "fixed" || t === "combined"; }

function formatPrice(n: number, currency = "KZT") {
  return `${new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n)} ${currency}`;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "2-digit", month: "short", year: "numeric" });
}

function SummaryCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: "20px 24px", flex: 1 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 800, color: color ?? "#0f172a", lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

export default function AdminCommissionsPage() {
  // ── Settings modal ────────────────────────────────────────────
  const [showSettings, setShowSettings] = useState(false);
  const [globalOpen, setGlobalOpen] = useState(false);

  const [configs, setConfigs] = useState<CommissionConfigResponse[]>([]);
  const [configsLoading, setConfigsLoading] = useState(false);
  const [configsError, setConfigsError] = useState<string | null>(null);

  const [editingCode, setEditingCode] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deletingCode, setDeletingCode] = useState<string | null>(null);

  const [settings, setSettings] = useState<PlatformSettings | null>(null);
  const [rateInput, setRateInput] = useState("");
  const [savingRate, setSavingRate] = useState(false);
  const [rateError, setRateError] = useState<string | null>(null);
  const [rateSaved, setRateSaved] = useState(false);

  // ── History ───────────────────────────────────────────────────
  const [items, setItems] = useState<AdminCommission[]>([]);
  const [summary, setSummary] = useState<CommissionSummary | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const SIZE = 50;

  // ── Load history ──────────────────────────────────────────────
  const loadHistory = useCallback(() => {
    setHistoryLoading(true);
    Promise.all([
      listAdminCommissions(page, SIZE),
      page === 1 ? getCommissionsSummary() : Promise.resolve(summary),
    ])
      .then(([res, sum]) => {
        setItems(res.items);
        setTotal(res.total);
        if (sum) setSummary(sum);
      })
      .catch((e: Error) => setHistoryError(e.message))
      .finally(() => setHistoryLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  // ── Load configs + global rate (when settings opens) ─────────
  function loadConfigs() {
    setConfigsLoading(true);
    listCommissionConfigs()
      .then(setConfigs)
      .catch((e: Error) => setConfigsError(e.message))
      .finally(() => setConfigsLoading(false));
  }

  function openSettings() {
    setShowSettings(true);
    loadConfigs();
    getAdminSettings()
      .then((s) => { setSettings(s); setRateInput(String(Number(s.commission_rate) * 100)); })
      .catch(() => {});
  }

  // ── Global rate save ──────────────────────────────────────────
  async function handleSaveRate(e: FormEvent) {
    e.preventDefault();
    setRateError(null); setRateSaved(false);
    const num = parseFloat(rateInput.replace(",", "."));
    if (isNaN(num) || num < 0 || num > 100) { setRateError("Введите число от 0 до 100"); return; }
    setSavingRate(true);
    try {
      const updated = await updateAdminSettings({ commission_rate: (num / 100).toFixed(4) });
      setSettings(updated);
      setRateInput(String(Number(updated.commission_rate) * 100));
      setRateSaved(true);
      setTimeout(() => setRateSaved(false), 3000);
    } catch (e: unknown) {
      setRateError(e instanceof Error ? e.message : "Ошибка");
    } finally { setSavingRate(false); }
  }

  // ── Per-carrier config CRUD ───────────────────────────────────
  function openNew() { setForm(EMPTY_FORM); setFormError(null); setEditingCode(""); }
  function openEdit(cfg: CommissionConfigResponse) {
    setForm({
      carrier_code:    cfg.carrier_code,
      commission_type: cfg.commission_type,
      commission_rate: cfg.commission_rate != null ? Number(cfg.commission_rate) * 100 : null,
      fixed_amount:    cfg.fixed_amount != null ? Number(cfg.fixed_amount) : null,
      currency:        cfg.currency,
    });
    setFormError(null);
    setEditingCode(cfg.carrier_code);
  }

  async function handleSaveConfig() {
    setFormError(null);
    if (!form.carrier_code.trim()) { setFormError("Укажите код перевозчика"); return; }
    if (typeNeedsRate(form.commission_type) && (form.commission_rate == null || isNaN(form.commission_rate))) {
      setFormError("Укажите процентную ставку"); return;
    }
    if (typeNeedsFixed(form.commission_type) && (form.fixed_amount == null || isNaN(form.fixed_amount))) {
      setFormError("Укажите фиксированную сумму"); return;
    }
    setSaving(true);
    try {
      await upsertCommissionConfig(form.carrier_code.trim().toUpperCase(), {
        commission_type: form.commission_type,
        commission_rate: typeNeedsRate(form.commission_type) ? (form.commission_rate! / 100) : null,
        fixed_amount:    typeNeedsFixed(form.commission_type) ? form.fixed_amount : null,
        currency:        form.currency.toUpperCase(),
      } as CommissionConfigUpsert);
      setEditingCode(null);
      loadConfigs();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Ошибка сохранения");
    } finally { setSaving(false); }
  }

  async function handleDeleteConfig(code: string) {
    setDeletingCode(code);
    try { await deleteCommissionConfig(code); loadConfigs(); }
    catch (e: unknown) { setConfigsError(e instanceof Error ? e.message : "Ошибка удаления"); }
    finally { setDeletingCode(null); }
  }

  const historyPages = Math.ceil(total / SIZE) || 1;
  const isNew = editingCode === "";

  return (
    <>
      {/* ── Summary cards ─────────────────────────────────────── */}
      <div style={{ display: "flex", gap: 16, alignItems: "stretch", marginBottom: 16 }}>
        {summary ? (
          <>
            <SummaryCard label="Общий оборот" value={formatPrice(summary.total_gross, summary.currency)} sub="сумма заказов" />
            <SummaryCard
              label="Комиссия Novex"
              value={formatPrice(summary.total_commission, summary.currency)}
              sub={settings ? `${(Number(settings.commission_rate) * 100).toFixed(2)}% от оборота` : "от оборота"}
              color="#16a34a"
            />
            <SummaryCard label="Транзакций" value={String(summary.count)} sub="оплаченных заказов" />
          </>
        ) : (
          <>
            {[0,1,2].map(i => (
              <div key={i} style={{ flex: 1, background: "#f8fafc", border: "1px solid #e5e7eb", borderRadius: 14, padding: "20px 24px", minHeight: 80 }} />
            ))}
          </>
        )}
      </div>

      {/* ── Settings button (below cards) ────────────────────── */}
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 28 }}>
        <button
          onClick={openSettings}
          style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: "9px 18px",
            borderRadius: 10,
            border: "1px solid #e5e7eb",
            background: "#fff",
            color: "#475569",
            fontSize: 13,
            fontWeight: 600,
            cursor: "pointer",
            fontFamily: "inherit",
            boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
          Настройки ставок
        </button>
      </div>

      {/* ── History error ─────────────────────────────────────── */}
      {historyError && (
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 10, padding: "12px 16px", color: "#b91c1c", fontSize: 14, marginBottom: 20 }}>
          {historyError}
        </div>
      )}

      {/* ── History table ─────────────────────────────────────── */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "80px 100px 140px 160px 160px 120px", gap: 12, padding: "12px 24px", background: "#f8fafc", borderBottom: "1px solid #e5e7eb", fontSize: 12, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          <span>ID</span><span>Заказ</span><span>Перевозчик</span><span>Сумма заказа</span><span>Комиссия</span><span>Дата</span>
        </div>

        {historyLoading ? (
          <div style={{ padding: 48, textAlign: "center", color: "#64748b", fontSize: 14 }}>Загружаем…</div>
        ) : items.length === 0 ? (
          <div style={{ padding: "48px 24px", textAlign: "center", color: "#64748b", fontSize: 14 }}>
            Записей пока нет - появятся после первой оплаты
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

      {historyPages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 20 }}>
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
            style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid #e5e7eb", background: "#fff", color: "#475569", fontSize: 13, fontWeight: 500, cursor: page === 1 ? "not-allowed" : "pointer", opacity: page === 1 ? 0.4 : 1, fontFamily: "inherit" }}
          >← Назад</button>
          <span style={{ padding: "7px 16px", fontSize: 13, color: "#64748b" }}>{page} / {historyPages}</span>
          <button
            onClick={() => setPage((p) => Math.min(historyPages, p + 1))} disabled={page === historyPages}
            style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid #e5e7eb", background: "#fff", color: "#475569", fontSize: 13, fontWeight: 500, cursor: page === historyPages ? "not-allowed" : "pointer", opacity: page === historyPages ? 0.4 : 1, fontFamily: "inherit" }}
          >Вперёд →</button>
        </div>
      )}

      {/* ── Settings modal ────────────────────────────────────── */}
      {showSettings && (
        <div
          onClick={(e) => { if (e.target === e.currentTarget) setShowSettings(false); }}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 50, display: "flex", alignItems: "flex-start", justifyContent: "flex-end" }}
        >
          <div style={{ background: "#fff", width: 520, height: "100%", overflowY: "auto", boxShadow: "-8px 0 40px rgba(0,0,0,0.12)", display: "flex", flexDirection: "column" }}>
            {/* Drawer header */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "24px 28px", borderBottom: "1px solid #f1f5f9", flexShrink: 0 }}>
              <div>
                <div style={{ fontSize: 18, fontWeight: 800, color: "#0f172a" }}>Настройки комиссий</div>
                <div style={{ fontSize: 13, color: "#64748b", marginTop: 2 }}>Ставки и конфигурации перевозчиков</div>
              </div>
              <button
                onClick={() => setShowSettings(false)}
                style={{ width: 32, height: 32, borderRadius: 8, border: "1px solid #e5e7eb", background: "#fff", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "#64748b", fontSize: 18, fontFamily: "inherit" }}
              >×</button>
            </div>

            <div style={{ padding: "24px 28px", flex: 1 }}>
              {/* Global rate accordion */}
              <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, marginBottom: 16, overflow: "hidden" }}>
                <button
                  onClick={() => setGlobalOpen((v) => !v)}
                  style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 18px", background: globalOpen ? "#f8fafc" : "#fff", border: "none", cursor: "pointer", fontFamily: "inherit", textAlign: "left" }}
                >
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>Глобальная ставка</div>
                    {!globalOpen && settings && (
                      <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 2 }}>
                        Текущая: {(Number(settings.commission_rate) * 100).toFixed(2)}%
                      </div>
                    )}
                  </div>
                  <svg
                    width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                    style={{ transform: globalOpen ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s", flexShrink: 0 }}
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>

                {globalOpen && (
                  <div style={{ padding: "4px 18px 18px", borderTop: "1px solid #f1f5f9" }}>
                    <div style={{ fontSize: 12, color: "#94a3b8", margin: "12px 0 14px" }}>
                      Применяется если у перевозчика нет индивидуальной настройки
                    </div>
                    <form onSubmit={(e) => void handleSaveRate(e)} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: "flex", alignItems: "center", border: "1px solid #e5e7eb", borderRadius: 10, overflow: "hidden", background: "#f8fafc" }}>
                          <input
                            type="number" min="0" max="100" step="0.01"
                            value={rateInput}
                            onChange={(e) => { setRateInput(e.target.value); setRateError(null); setRateSaved(false); }}
                            style={{ flex: 1, border: "none", background: "transparent", padding: "10px 12px", fontSize: 16, fontWeight: 700, color: "#0f172a", outline: "none", fontFamily: "inherit" }}
                          />
                          <span style={{ padding: "10px 14px 10px 0", fontSize: 16, fontWeight: 700, color: "#64748b" }}>%</span>
                        </div>
                        {rateError && <div style={{ fontSize: 12, color: "#dc2626", marginTop: 4 }}>{rateError}</div>}
                        {rateSaved && <div style={{ fontSize: 12, color: "#16a34a", marginTop: 4 }}>Сохранено</div>}
                      </div>
                      <button
                        type="submit" disabled={savingRate}
                        style={{ padding: "10px 18px", borderRadius: 10, border: "none", background: "#0f172a", color: "#fff", fontSize: 13, fontWeight: 600, cursor: savingRate ? "not-allowed" : "pointer", opacity: savingRate ? 0.6 : 1, fontFamily: "inherit" }}
                      >{savingRate ? "…" : "Сохранить"}</button>
                    </form>
                  </div>
                )}
              </div>

              {/* Per-carrier configs */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>Индивидуальные ставки</div>
                  <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 2 }}>Переопределяют глобальную по перевозчику</div>
                </div>
                <button
                  onClick={openNew}
                  style={{ padding: "7px 14px", borderRadius: 9, border: "none", background: "#0f172a", color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
                >+ Добавить</button>
              </div>

              {configsError && (
                <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, padding: "10px 14px", color: "#b91c1c", fontSize: 13, marginBottom: 12 }}>
                  {configsError}
                </div>
              )}

              {configsLoading ? (
                <div style={{ padding: "24px 0", textAlign: "center", color: "#94a3b8", fontSize: 13 }}>Загружаем…</div>
              ) : configs.length === 0 ? (
                <div style={{ padding: "24px 0", textAlign: "center", color: "#94a3b8", fontSize: 13 }}>
                  Нет настроек - используется глобальная ставка
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {configs.map((cfg) => (
                    <div
                      key={cfg.id}
                      style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", background: "#f8fafc", borderRadius: 12, border: "1px solid #e5e7eb" }}
                    >
                      <div>
                        <span style={{ fontSize: 14, fontWeight: 700, color: "#0f172a", fontFamily: "monospace" }}>{cfg.carrier_code}</span>
                        <span style={{ fontSize: 12, color: "#64748b", marginLeft: 10 }}>{TYPE_LABELS[cfg.commission_type]}</span>
                        <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 3 }}>
                          {cfg.commission_rate != null && `${(Number(cfg.commission_rate) * 100).toFixed(2)}%`}
                          {cfg.commission_rate != null && cfg.fixed_amount != null && " + "}
                          {cfg.fixed_amount != null && `${Number(cfg.fixed_amount).toLocaleString("ru-RU")} ${cfg.currency}`}
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: 6 }}>
                        <button
                          onClick={() => openEdit(cfg)}
                          style={{ padding: "5px 12px", borderRadius: 8, border: "1px solid #e5e7eb", background: "#fff", color: "#0f172a", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
                        >Изм.</button>
                        <button
                          onClick={() => void handleDeleteConfig(cfg.carrier_code)}
                          disabled={deletingCode === cfg.carrier_code}
                          style={{ padding: "5px 12px", borderRadius: 8, border: "1px solid #fecaca", background: "#fff", color: "#dc2626", fontSize: 12, fontWeight: 600, cursor: deletingCode === cfg.carrier_code ? "not-allowed" : "pointer", opacity: deletingCode === cfg.carrier_code ? 0.5 : 1, fontFamily: "inherit" }}
                        >Удал.</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Config edit modal (z-60, above drawer) ───────────── */}
      {editingCode !== null && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)", zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ background: "#fff", borderRadius: 18, padding: "32px 36px", width: 400, boxShadow: "0 20px 60px rgba(0,0,0,0.18)" }}>
            <h2 style={{ margin: "0 0 22px", fontSize: 18, fontWeight: 800, color: "#0f172a" }}>
              {isNew ? "Новая ставка" : `Редактировать: ${editingCode}`}
            </h2>

            {isNew && (
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                  Код перевозчика
                </label>
                <input
                  value={form.carrier_code}
                  onChange={(e) => setForm((f) => ({ ...f, carrier_code: e.target.value }))}
                  placeholder="DHL, SDEK, ..."
                  style={{ width: "100%", padding: "10px 14px", borderRadius: 10, border: "1px solid #cbd5e1", fontSize: 14, boxSizing: "border-box", fontFamily: "inherit" }}
                />
              </div>
            )}

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                Тип комиссии
              </label>
              <select
                value={form.commission_type}
                onChange={(e) => setForm((f) => ({ ...f, commission_type: e.target.value as CommissionType }))}
                style={{ width: "100%", padding: "10px 14px", borderRadius: 10, border: "1px solid #cbd5e1", fontSize: 14, background: "#fff", fontFamily: "inherit" }}
              >
                <option value="percentage">Процент от суммы заказа</option>
                <option value="fixed">Фиксированная сумма</option>
                <option value="combined">Комбинированная (% + фиксированная)</option>
              </select>
            </div>

            {typeNeedsRate(form.commission_type) && (
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                  Ставка (%)
                </label>
                <div style={{ display: "flex", alignItems: "center", border: "1px solid #cbd5e1", borderRadius: 10, overflow: "hidden", background: "#f8fafc" }}>
                  <input
                    type="number" min="0" max="100" step="0.01"
                    value={form.commission_rate ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, commission_rate: e.target.value === "" ? null : parseFloat(e.target.value) }))}
                    style={{ flex: 1, border: "none", background: "transparent", padding: "10px 14px", fontSize: 14, fontWeight: 700, color: "#0f172a", outline: "none", fontFamily: "inherit" }}
                  />
                  <span style={{ padding: "10px 14px 10px 0", fontSize: 14, fontWeight: 700, color: "#64748b" }}>%</span>
                </div>
              </div>
            )}

            {typeNeedsFixed(form.commission_type) && (
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                  Фиксированная сумма
                </label>
                <div style={{ display: "flex", alignItems: "center", border: "1px solid #cbd5e1", borderRadius: 10, overflow: "hidden", background: "#f8fafc" }}>
                  <input
                    type="number" min="0" step="0.01"
                    value={form.fixed_amount ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, fixed_amount: e.target.value === "" ? null : parseFloat(e.target.value) }))}
                    style={{ flex: 1, border: "none", background: "transparent", padding: "10px 14px", fontSize: 14, fontWeight: 700, color: "#0f172a", outline: "none", fontFamily: "inherit" }}
                  />
                  <span style={{ padding: "10px 14px 10px 0", fontSize: 14, fontWeight: 600, color: "#64748b" }}>{form.currency}</span>
                </div>
              </div>
            )}

            <div style={{ marginBottom: 22 }}>
              <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                Валюта
              </label>
              <input
                value={form.currency}
                onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))}
                maxLength={3}
                style={{ width: 90, padding: "10px 14px", borderRadius: 10, border: "1px solid #cbd5e1", fontSize: 14, fontFamily: "inherit", textTransform: "uppercase" }}
              />
            </div>

            {formError && <div style={{ color: "#b91c1c", fontSize: 13, marginBottom: 14 }}>{formError}</div>}

            <div style={{ display: "flex", gap: 10 }}>
              <button
                onClick={() => void handleSaveConfig()} disabled={saving}
                style={{ flex: 1, padding: 11, borderRadius: 10, border: "none", background: "#0f172a", color: "#fff", fontSize: 14, fontWeight: 600, cursor: saving ? "not-allowed" : "pointer", opacity: saving ? 0.6 : 1, fontFamily: "inherit" }}
              >{saving ? "Сохраняем..." : "Сохранить"}</button>
              <button
                onClick={() => setEditingCode(null)}
                style={{ padding: "11px 20px", borderRadius: 10, border: "1px solid #e5e7eb", background: "#fff", color: "#475569", fontSize: 14, fontWeight: 500, cursor: "pointer", fontFamily: "inherit" }}
              >Отмена</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
