"use client";

import { useEffect, useState } from "react";

import {
  deleteCommissionConfig,
  listCommissionConfigs,
  upsertCommissionConfig,
  type CommissionConfigResponse,
  type CommissionConfigUpsert,
  type CommissionType,
} from "@/lib/api/commission_configs";
import { errorMessage } from "@/lib/api/client";

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

export default function AdminCommissionConfigsPage() {
  const [configs, setConfigs] = useState<CommissionConfigResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editingCode, setEditingCode] = useState<string | null>(null); // null = closed, "" = new
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deletingCode, setDeletingCode] = useState<string | null>(null);

  function load() {
    setIsLoading(true);
    listCommissionConfigs()
      .then(setConfigs)
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }

  useEffect(load, []);

  function openNew() {
    setForm(EMPTY_FORM);
    setFormError(null);
    setEditingCode("");
  }

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

  async function handleSave() {
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
      const payload: CommissionConfigUpsert = {
        commission_type: form.commission_type,
        commission_rate: typeNeedsRate(form.commission_type)
          ? (form.commission_rate! / 100)
          : null,
        fixed_amount: typeNeedsFixed(form.commission_type) ? form.fixed_amount : null,
        currency: form.currency.toUpperCase(),
      };
      await upsertCommissionConfig(form.carrier_code.trim().toUpperCase(), payload);
      setEditingCode(null);
      load();
    } catch (e: unknown) {
      setFormError(errorMessage(e, "Ошибка сохранения"));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(carrierCode: string) {
    setDeletingCode(carrierCode);
    try {
      await deleteCommissionConfig(carrierCode);
      load();
    } catch (e: unknown) {
      setError(errorMessage(e, "Ошибка удаления"));
    } finally {
      setDeletingCode(null);
    }
  }

  const isNew = editingCode === "";

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: "#0B2545" }}>
            Комиссии перевозчиков
          </h1>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>
            Индивидуальные настройки комиссии по каждому перевозчику
          </p>
        </div>
        <button
          onClick={openNew}
          style={{ padding: "10px 20px", borderRadius: 10, border: "none", background: "#0B2545", color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
        >
          + Добавить
        </button>
      </div>

      {error && (
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 10, padding: "12px 16px", color: "#b91c1c", fontSize: 14, marginBottom: 20 }}>
          {error}
        </div>
      )}

      {/* Modal / inline form */}
      {editingCode !== null && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)", zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ background: "#fff", borderRadius: 18, padding: "32px 36px", width: 420, boxShadow: "0 20px 60px rgba(0,0,0,0.15)" }}>
            <h2 style={{ margin: "0 0 22px", fontSize: 20, fontWeight: 800, color: "#0B2545" }}>
              {isNew ? "Новая конфигурация" : `Редактировать: ${editingCode}`}
            </h2>

            {/* Carrier code (only for new) */}
            {isNew && (
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: "block", fontSize: 12, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 6 }}>
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

            {/* Type selector */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", fontSize: 12, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 6 }}>
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

            {/* Rate */}
            {typeNeedsRate(form.commission_type) && (
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: "block", fontSize: 12, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 6 }}>
                  Ставка (%)
                </label>
                <div style={{ display: "flex", alignItems: "center", border: "1px solid #cbd5e1", borderRadius: 10, overflow: "hidden", background: "#f8fafc" }}>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="0.01"
                    value={form.commission_rate ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, commission_rate: e.target.value === "" ? null : parseFloat(e.target.value) }))}
                    style={{ flex: 1, border: "none", background: "transparent", padding: "10px 14px", fontSize: 14, fontWeight: 700, color: "#0B2545", outline: "none", fontFamily: "inherit" }}
                  />
                  <span style={{ padding: "10px 14px 10px 0", fontSize: 14, fontWeight: 700, color: "#64748b" }}>%</span>
                </div>
              </div>
            )}

            {/* Fixed amount */}
            {typeNeedsFixed(form.commission_type) && (
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: "block", fontSize: 12, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 6 }}>
                  Фиксированная сумма
                </label>
                <div style={{ display: "flex", alignItems: "center", border: "1px solid #cbd5e1", borderRadius: 10, overflow: "hidden", background: "#f8fafc" }}>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={form.fixed_amount ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, fixed_amount: e.target.value === "" ? null : parseFloat(e.target.value) }))}
                    style={{ flex: 1, border: "none", background: "transparent", padding: "10px 14px", fontSize: 14, fontWeight: 700, color: "#0B2545", outline: "none", fontFamily: "inherit" }}
                  />
                  <span style={{ padding: "10px 14px 10px 0", fontSize: 14, fontWeight: 600, color: "#64748b" }}>{form.currency}</span>
                </div>
              </div>
            )}

            {/* Currency */}
            <div style={{ marginBottom: 22 }}>
              <label style={{ display: "block", fontSize: 12, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 6 }}>
                Валюта
              </label>
              <input
                value={form.currency}
                onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))}
                maxLength={3}
                style={{ width: 100, padding: "10px 14px", borderRadius: 10, border: "1px solid #cbd5e1", fontSize: 14, fontFamily: "inherit", textTransform: "uppercase" }}
              />
            </div>

            {formError && (
              <div style={{ color: "#b91c1c", fontSize: 13, marginBottom: 14 }}>{formError}</div>
            )}

            <div style={{ display: "flex", gap: 10 }}>
              <button
                onClick={() => void handleSave()}
                disabled={saving}
                style={{ flex: 1, padding: "11px", borderRadius: 10, border: "none", background: "#0B2545", color: "#fff", fontSize: 14, fontWeight: 600, cursor: saving ? "not-allowed" : "pointer", opacity: saving ? 0.6 : 1, fontFamily: "inherit" }}
              >
                {saving ? "Сохраняем..." : "Сохранить"}
              </button>
              <button
                onClick={() => setEditingCode(null)}
                style={{ padding: "11px 20px", borderRadius: 10, border: "1px solid #E2E8EE", background: "#fff", color: "#475569", fontSize: 14, fontWeight: 500, cursor: "pointer", fontFamily: "inherit" }}
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Table */}
      <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "160px 160px 130px 130px 90px 100px", gap: 12, padding: "12px 24px", background: "#f8fafc", borderBottom: "1px solid #E2E8EE", fontSize: 12, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          <span>Перевозчик</span>
          <span>Тип</span>
          <span>Ставка</span>
          <span>Фикс. сумма</span>
          <span>Валюта</span>
          <span>Действия</span>
        </div>

        {isLoading ? (
          <div style={{ padding: 48, textAlign: "center", color: "#64748b", fontSize: 14 }}>Загружаем…</div>
        ) : configs.length === 0 ? (
          <div style={{ padding: "48px 24px", textAlign: "center", color: "#64748b", fontSize: 14 }}>
            Нет настроек - используется глобальная ставка из настроек платформы
          </div>
        ) : (
          configs.map((cfg, idx) => (
            <div
              key={cfg.id}
              style={{ display: "grid", gridTemplateColumns: "160px 160px 130px 130px 90px 100px", gap: 12, padding: "14px 24px", borderBottom: idx === configs.length - 1 ? "none" : "1px solid #f1f5f9", alignItems: "center" }}
            >
              <span style={{ fontSize: 14, fontWeight: 700, color: "#0B2545", fontFamily: "monospace" }}>
                {cfg.carrier_code}
              </span>
              <span style={{ fontSize: 13, color: "#475569" }}>
                {TYPE_LABELS[cfg.commission_type]}
              </span>
              <span style={{ fontSize: 13, color: "#0B2545", fontWeight: 600 }}>
                {cfg.commission_rate != null
                  ? `${(Number(cfg.commission_rate) * 100).toFixed(2)}%`
                  : "-"}
              </span>
              <span style={{ fontSize: 13, color: "#0B2545", fontWeight: 600 }}>
                {cfg.fixed_amount != null
                  ? `${Number(cfg.fixed_amount).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${cfg.currency}`
                  : "-"}
              </span>
              <span style={{ fontSize: 13, color: "#64748b" }}>{cfg.currency}</span>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={() => openEdit(cfg)}
                  style={{ padding: "5px 12px", borderRadius: 8, border: "1px solid #E2E8EE", background: "#fff", color: "#0B2545", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
                >
                  Изм.
                </button>
                <button
                  onClick={() => void handleDelete(cfg.carrier_code)}
                  disabled={deletingCode === cfg.carrier_code}
                  style={{ padding: "5px 12px", borderRadius: 8, border: "1px solid #fecaca", background: "#fff", color: "#dc2626", fontSize: 12, fontWeight: 600, cursor: deletingCode === cfg.carrier_code ? "not-allowed" : "pointer", opacity: deletingCode === cfg.carrier_code ? 0.5 : 1, fontFamily: "inherit" }}
                >
                  Удал.
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Info note */}
      <div style={{ marginTop: 20, padding: "14px 18px", background: "#f8fafc", border: "1px solid #E2E8EE", borderRadius: 12, fontSize: 13, color: "#64748b" }}>
        <strong style={{ color: "#475569" }}>Как работает:</strong>{" "}
        Если для перевозчика задана конфигурация, она используется при расчёте комиссии вместо глобальной ставки. Ставка задаётся в процентах от суммы заказа, фиксированная - в абсолютной сумме.
      </div>
    </>
  );
}
