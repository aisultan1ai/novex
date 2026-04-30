"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { createAdminCarrier, listAdminCarriers, updateAdminCarrier } from "@/lib/api/admin";
import type { AdminCarrier } from "@/types/admin";

export default function AdminCarriersPage() {
  const [carriers, setCarriers] = useState<AdminCarrier[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  const [form, setForm] = useState({ code: "", name: "", description: "" });

  function load() {
    setIsLoading(true);
    listAdminCarriers()
      .then(setCarriers)
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await createAdminCarrier({ code: form.code.trim(), name: form.name.trim(), description: form.description.trim() || undefined });
      setForm({ code: "", name: "", description: "" });
      setShowForm(false);
      load();
    } catch (err: unknown) {
      alert((err as Error).message);
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
      alert((e as Error).message);
    } finally {
      setTogglingId(null);
    }
  }

  const inp: React.CSSProperties = { border: "1px solid #e5e7eb", borderRadius: 10, padding: "10px 14px", fontSize: 14, width: "100%", boxSizing: "border-box", fontFamily: "inherit", outline: "none", background: "#f8fafc", color: "#0f172a" };

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0f172a" }}>Перевозчики</h2>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>Управление перевозчиками и тарифными сетками</p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          style={{ padding: "10px 20px", borderRadius: 10, border: "none", background: "#0f172a", color: "#ffffff", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
        >
          {showForm ? "Отмена" : "+ Добавить перевозчика"}
        </button>
      </div>

      {error && <div style={{ padding: "12px 16px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 14, marginBottom: 20 }}>{error}</div>}

      {showForm && (
        <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, padding: "24px 28px", marginBottom: 24 }}>
          <h3 style={{ margin: "0 0 20px", fontSize: 16, fontWeight: 700, color: "#0f172a" }}>Новый перевозчик</h3>
          <form onSubmit={handleCreate}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#334155", marginBottom: 8 }}>Код (латиница, уникальный)</label>
                <input style={inp} value={form.code} onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))} placeholder="azimuth" required pattern="[a-z0-9_-]+" />
              </div>
              <div>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#334155", marginBottom: 8 }}>Название</label>
                <input style={inp} value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="Azimuth" required />
              </div>
              <div style={{ gridColumn: "1 / -1" }}>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#334155", marginBottom: 8 }}>Описание (необязательно)</label>
                <input style={inp} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} placeholder="Казахстанская курьерская служба" />
              </div>
            </div>
            <button type="submit" disabled={saving} style={{ padding: "10px 24px", borderRadius: 10, border: "none", background: "#0f172a", color: "#ffffff", fontSize: 14, fontWeight: 600, cursor: saving ? "not-allowed" : "pointer", opacity: saving ? 0.7 : 1, fontFamily: "inherit" }}>
              {saving ? "Создаём..." : "Создать"}
            </button>
          </form>
        </div>
      )}

      {isLoading ? (
        <div style={{ padding: 48, textAlign: "center", color: "#64748b" }}>Загружаем…</div>
      ) : carriers.length === 0 ? (
        <div style={{ padding: 48, textAlign: "center", color: "#94a3b8", background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16 }}>Перевозчиков нет</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {carriers.map((carrier) => (
            <div
              key={carrier.id}
              style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 14, padding: "20px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                <div style={{ width: 48, height: 48, borderRadius: 10, background: "#f1f5f9", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, fontWeight: 800, color: "#0f172a", flexShrink: 0 }}>
                  {carrier.name[0]}
                </div>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 16, fontWeight: 700, color: "#0f172a" }}>{carrier.name}</span>
                    <span style={{ fontFamily: "monospace", fontSize: 12, color: "#94a3b8", background: "#f1f5f9", padding: "2px 8px", borderRadius: 6 }}>{carrier.code}</span>
                    <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: carrier.is_active ? "#dcfce7" : "#f1f5f9", color: carrier.is_active ? "#166534" : "#94a3b8" }}>
                      {carrier.is_active ? "Активен" : "Неактивен"}
                    </span>
                  </div>
                  {carrier.description && <div style={{ fontSize: 13, color: "#64748b", marginTop: 4 }}>{carrier.description}</div>}
                </div>
              </div>

              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <Link
                  href={`/dashboard/admin/carriers/${carrier.id}`}
                  style={{ padding: "8px 16px", borderRadius: 10, border: "1px solid #e5e7eb", background: "#ffffff", color: "#0f172a", fontSize: 13, fontWeight: 600, textDecoration: "none" }}
                >
                  Тарифы →
                </Link>
                <button
                  onClick={() => void toggleActive(carrier)}
                  disabled={togglingId === carrier.id}
                  style={{ padding: "8px 14px", borderRadius: 10, border: `1px solid ${carrier.is_active ? "#fecaca" : "#bbf7d0"}`, background: carrier.is_active ? "#fef2f2" : "#f0fdf4", color: carrier.is_active ? "#b91c1c" : "#166534", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", opacity: togglingId === carrier.id ? 0.5 : 1 }}
                >
                  {carrier.is_active ? "Деактивировать" : "Активировать"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
