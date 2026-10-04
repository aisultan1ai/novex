"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { createAdminCarrier, createCarrierAccount, listAdminCarriers, updateAdminCarrier } from "@/lib/api/admin";
import type { AdminCarrier } from "@/types/admin";
import { useIsAdmin } from "@/hooks/use-is-admin";

const inp: React.CSSProperties = {
  border: "1px solid #E2E8EE", borderRadius: 10, padding: "10px 14px",
  fontSize: 14, width: "100%", boxSizing: "border-box",
  fontFamily: "inherit", outline: "none", background: "#f8fafc", color: "#0B2545",
};

const EMPTY_CARRIER = { code: "", name: "", description: "" };
const EMPTY_ACCOUNT = { email: "", full_name: "", temp_password: "" };

export default function AdminCarriersPage() {
  const isAdmin = useIsAdmin();
  const [carriers, setCarriers] = useState<AdminCarrier[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add carrier form
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_CARRIER);
  const [withAccount, setWithAccount] = useState(false);
  const [accountForm, setAccountForm] = useState(EMPTY_ACCOUNT);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [togglingId, setTogglingId] = useState<number | null>(null);

  function load() {
    setIsLoading(true);
    listAdminCarriers()
      .then(setCarriers)
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }

  useEffect(() => { load(); }, []);

  function openForm() {
    setForm(EMPTY_CARRIER);
    setAccountForm(EMPTY_ACCOUNT);
    setWithAccount(false);
    setFormError(null);
    setShowForm(true);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSaving(true);
    try {
      const carrier = await createAdminCarrier({
        code: form.code.trim(),
        name: form.name.trim(),
        description: form.description.trim() || undefined,
      });
      if (withAccount) {
        await createCarrierAccount(carrier.id, {
          email: accountForm.email.trim(),
          full_name: accountForm.full_name.trim() || undefined,
          temp_password: accountForm.temp_password,
        });
      }
      setShowForm(false);
      load();
    } catch (err: unknown) {
      setFormError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(carrier: AdminCarrier) {
    setTogglingId(carrier.id);
    try {
      await updateAdminCarrier(carrier.id, { is_active: !carrier.is_active });
      load();
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setTogglingId(null);
    }
  }

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0B2545" }}>Перевозчики</h2>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>Управление перевозчиками и тарифными сетками</p>
        </div>
        {isAdmin && !showForm && (
          <button
            onClick={openForm}
            style={{ padding: "10px 20px", borderRadius: 10, border: "none", background: "#0B2545", color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
          >
            + Добавить перевозчика
          </button>
        )}
      </div>

      {error && (
        <div style={{ padding: "12px 16px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 14, marginBottom: 20 }}>
          {error}
        </div>
      )}

      {/* Add carrier form */}
      {showForm && (
        <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, padding: "28px 32px", marginBottom: 24 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 22 }}>
            <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "#0B2545" }}>Новый перевозчик</h3>
            <button onClick={() => setShowForm(false)} style={{ background: "none", border: "none", cursor: "pointer", color: "#94a3b8", fontSize: 22, lineHeight: 1, padding: 4 }}>×</button>
          </div>

          <form onSubmit={(e) => void handleCreate(e)}>
            {/* Carrier fields */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#334155", marginBottom: 6 }}>Код <span style={{ color: "#94a3b8", fontWeight: 400 }}>(латиница)</span></label>
                <input style={inp} value={form.code} onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))} placeholder="azimuth" required pattern="[a-z0-9_-]+" />
              </div>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#334155", marginBottom: 6 }}>Название</label>
                <input style={inp} value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="Azimuth" required />
              </div>
              <div style={{ gridColumn: "1 / -1" }}>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#334155", marginBottom: 6 }}>Описание <span style={{ color: "#94a3b8", fontWeight: 400 }}>(необязательно)</span></label>
                <input style={inp} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} placeholder="Казахстанская курьерская служба" />
              </div>
            </div>

            {/* Account toggle */}
            <div
              onClick={() => setWithAccount((v) => !v)}
              style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer", padding: "14px 16px", borderRadius: 12, border: `1px solid ${withAccount ? "#c7d2fe" : "#E2E8EE"}`, background: withAccount ? "#eef2ff" : "#f8fafc", marginBottom: withAccount ? 16 : 24, userSelect: "none", transition: "all 0.15s" }}
            >
              <div style={{ width: 20, height: 20, borderRadius: 6, border: `2px solid ${withAccount ? "#6366f1" : "#cbd5e1"}`, background: withAccount ? "#6366f1" : "#fff", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "all 0.15s" }}>
                {withAccount && <svg width="11" height="11" viewBox="0 0 12 12" fill="none"><polyline points="2 6 5 9 10 3" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>}
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: "#0B2545" }}>Создать аккаунт для перевозчика</div>
                <div style={{ fontSize: 12, color: "#64748b" }}>Перевозчик сможет войти в личный кабинет и получать уведомления</div>
              </div>
            </div>

            {/* Account fields (conditional) */}
            {withAccount && (
              <div style={{ background: "#f8fafc", border: "1px solid #E2E8EE", borderRadius: 12, padding: "18px 20px", marginBottom: 20 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 14 }}>Данные аккаунта</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                  <div>
                    <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#334155", marginBottom: 6 }}>Email</label>
                    <input style={inp} type="email" required={withAccount} value={accountForm.email} onChange={(e) => setAccountForm((f) => ({ ...f, email: e.target.value }))} placeholder="carrier@example.com" />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#334155", marginBottom: 6 }}>Имя <span style={{ color: "#94a3b8", fontWeight: 400 }}>(необязательно)</span></label>
                    <input style={inp} value={accountForm.full_name} onChange={(e) => setAccountForm((f) => ({ ...f, full_name: e.target.value }))} placeholder="Иван Иванов" />
                  </div>
                  <div style={{ gridColumn: "1 / -1" }}>
                    <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#334155", marginBottom: 6 }}>Временный пароль</label>
                    <input style={inp} required={withAccount} minLength={8} value={accountForm.temp_password} onChange={(e) => setAccountForm((f) => ({ ...f, temp_password: e.target.value }))} placeholder="Минимум 8 символов" />
                  </div>
                </div>
              </div>
            )}

            {formError && (
              <div style={{ fontSize: 13, color: "#b91c1c", marginBottom: 14 }}>{formError}</div>
            )}

            <div style={{ display: "flex", gap: 10 }}>
              <button type="submit" disabled={saving} style={{ padding: "10px 28px", borderRadius: 10, border: "none", background: "#0B2545", color: "#fff", fontSize: 14, fontWeight: 600, cursor: saving ? "not-allowed" : "pointer", opacity: saving ? 0.7 : 1, fontFamily: "inherit" }}>
                {saving ? "Создаём..." : withAccount ? "Создать перевозчика и аккаунт" : "Создать перевозчика"}
              </button>
              <button type="button" onClick={() => setShowForm(false)} style={{ padding: "10px 20px", borderRadius: 10, border: "1px solid #E2E8EE", background: "#fff", color: "#64748b", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
                Отмена
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Carriers list */}
      {isLoading ? (
        <div style={{ padding: 48, textAlign: "center", color: "#64748b" }}>Загружаем…</div>
      ) : carriers.length === 0 ? (
        <div style={{ padding: 48, textAlign: "center", color: "#94a3b8", background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16 }}>Перевозчиков нет</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {carriers.map((carrier) => (
            <div key={carrier.id} style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 14, padding: "20px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                <div style={{ width: 48, height: 48, borderRadius: 10, background: "#f1f5f9", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, fontWeight: 800, color: "#0B2545", flexShrink: 0 }}>
                  {carrier.name[0]}
                </div>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 16, fontWeight: 700, color: "#0B2545" }}>{carrier.name}</span>
                    <span style={{ fontFamily: "monospace", fontSize: 12, color: "#94a3b8", background: "#f1f5f9", padding: "2px 8px", borderRadius: 6 }}>{carrier.code}</span>
                    <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: carrier.is_active ? "#dcfce7" : "#f1f5f9", color: carrier.is_active ? "#166534" : "#94a3b8" }}>
                      {carrier.is_active ? "Активен" : "Неактивен"}
                    </span>
                  </div>
                  {carrier.description && <div style={{ fontSize: 13, color: "#64748b", marginTop: 4 }}>{carrier.description}</div>}
                </div>
              </div>

              <div style={{ display: "flex", gap: 8, alignItems: "center", flexShrink: 0 }}>
                <Link
                  href={`/dashboard/admin/carriers/${carrier.id}`}
                  style={{ padding: "8px 16px", borderRadius: 10, border: "1px solid #E2E8EE", background: "#fff", color: "#0B2545", fontSize: 13, fontWeight: 600, textDecoration: "none" }}
                >
                  Тарифы →
                </Link>
                {isAdmin && (
                  <button
                    onClick={() => void toggleActive(carrier)}
                    disabled={togglingId === carrier.id}
                    style={{ padding: "8px 14px", borderRadius: 10, border: `1px solid ${carrier.is_active ? "#fecaca" : "#bbf7d0"}`, background: carrier.is_active ? "#fef2f2" : "#f0fdf4", color: carrier.is_active ? "#b91c1c" : "#166534", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", opacity: togglingId === carrier.id ? 0.5 : 1 }}
                  >
                    {carrier.is_active ? "Деактивировать" : "Активировать"}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

    </>
  );
}
