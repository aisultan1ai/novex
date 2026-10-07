"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { useIsMobile } from "@/hooks/use-is-mobile";
import { createAddress, deleteAddress, listAddresses } from "@/lib/api/address_book";
import type { AddressEntry, AddressEntryCreate } from "@/types/address_book";
import { errorMessage } from "@/lib/api/client";

const inp: React.CSSProperties = {
  border: "1px solid #E2E8EE",
  borderRadius: 10,
  padding: "10px 14px",
  fontSize: 14,
  background: "#f8fafc",
  width: "100%",
  boxSizing: "border-box",
  outline: "none",
  fontFamily: "inherit",
  color: "#0E1826",
};

const lbl: React.CSSProperties = {
  display: "block",
  fontSize: 13,
  fontWeight: 600,
  color: "#334155",
  marginBottom: 6,
};

const EMPTY: AddressEntryCreate = {
  label: "",
  full_name: "",
  phone: "",
  email: "",
  company_name: "",
  tax_id: "",
  country: "KZ",
  city: "",
  address_line1: "",
  address_line2: "",
  postal_code: "",
  is_default: false,
};

function IconTrash() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  );
}

function IconPlus() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

export default function AddressBookPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const isMobile = useIsMobile();

  const [addresses, setAddresses] = useState<AddressEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<AddressEntryCreate>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push("/login");
  }, [isAuthenticated, authLoading, router]);

  useEffect(() => {
    if (!isAuthenticated) return;
    listAddresses()
      .then(setAddresses)
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, [isAuthenticated]);

  function setField(key: keyof AddressEntryCreate, value: string | boolean) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    const taxCleaned = (form.tax_id ?? "").trim();
    if (taxCleaned && !/^\d{12}$/.test(taxCleaned)) {
      setFormError("ИИН / БИН должен состоять ровно из 12 цифр");
      return;
    }
    setSaving(true);
    try {
      const payload: AddressEntryCreate = {
        ...form,
        label: form.label?.trim() || null,
        email: form.email?.trim() || null,
        company_name: form.company_name?.trim() || null,
        tax_id: taxCleaned || null,
        address_line2: form.address_line2?.trim() || null,
        postal_code: form.postal_code?.trim() || null,
        country: (form.country || "KZ").toUpperCase(),
      };
      const created = await createAddress(payload);
      setAddresses((prev) => [
        ...prev.map((a) => payload.is_default ? { ...a, is_default: false } : a),
        created,
      ]);
      setShowForm(false);
      setForm(EMPTY);
    } catch (e: unknown) {
      setFormError(errorMessage(e, "Ошибка при сохранении"));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    setDeletingId(id);
    setConfirmDeleteId(null);
    try {
      await deleteAddress(id);
      setAddresses((prev) => prev.filter((a) => a.id !== id));
    } catch (e: unknown) {
      setError(errorMessage(e, "Не удалось удалить"));
    } finally {
      setDeletingId(null);
    }
  }

  if (authLoading || (!isAuthenticated && !authLoading)) return null;

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: isMobile ? 16 : 24, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: isMobile ? 22 : 28, fontWeight: 800, color: "#0E1826" }}>Адресная книга</h1>
          <p style={{ margin: "4px 0 0", fontSize: isMobile ? 13 : 14, color: "#64748b" }}>
            Сохранённые адреса отправителя и получателя
          </p>
        </div>
        <button
          onClick={() => { setShowForm(!showForm); setFormError(null); }}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: isMobile ? "8px 14px" : "9px 18px",
            borderRadius: 10,
            border: "none",
            background: "#0E1826",
            color: "#fff",
            fontSize: isMobile ? 13 : 14,
            fontWeight: 600,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          <IconPlus /> {isMobile ? "Добавить" : "Добавить адрес"}
        </button>
      </div>

      {error && (
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 10, padding: "12px 16px", color: "#b91c1c", fontSize: 14, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {/* Form */}
      {showForm && (
        <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, padding: isMobile ? 18 : 28, marginBottom: 20 }}>
          <h2 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 700, color: "#0E1826" }}>
            Новый адрес
          </h2>
          <form onSubmit={(e) => void handleSubmit(e)}>
            <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: isMobile ? 12 : 16, marginBottom: 16 }}>
              <div>
                <label style={lbl}>Метка (необязательно)</label>
                <input style={inp} placeholder="Офис / Склад / Дом" value={form.label ?? ""} onChange={(e) => setField("label", e.target.value)}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "#0E1826"; e.currentTarget.style.background = "#fff"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "#E2E8EE"; e.currentTarget.style.background = "#f8fafc"; }}
                />
              </div>
              <div>
                <label style={lbl}>Контактное лицо *</label>
                <input style={inp} required placeholder="Иван Иванов" value={form.full_name} onChange={(e) => setField("full_name", e.target.value)}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "#0E1826"; e.currentTarget.style.background = "#fff"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "#E2E8EE"; e.currentTarget.style.background = "#f8fafc"; }}
                />
              </div>
              <div>
                <label style={lbl}>Телефон *</label>
                <input style={inp} required placeholder="+7 700 000 0000" value={form.phone} onChange={(e) => setField("phone", e.target.value)}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "#0E1826"; e.currentTarget.style.background = "#fff"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "#E2E8EE"; e.currentTarget.style.background = "#f8fafc"; }}
                />
              </div>
              <div>
                <label style={lbl}>Email</label>
                <input style={inp} type="email" placeholder="ivan@example.com" value={form.email ?? ""} onChange={(e) => setField("email", e.target.value)}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "#0E1826"; e.currentTarget.style.background = "#fff"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "#E2E8EE"; e.currentTarget.style.background = "#f8fafc"; }}
                />
              </div>
              <div>
                <label style={lbl}>Компания</label>
                <input style={inp} placeholder="ТОО «Компания»" value={form.company_name ?? ""} onChange={(e) => setField("company_name", e.target.value)}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "#0E1826"; e.currentTarget.style.background = "#fff"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "#E2E8EE"; e.currentTarget.style.background = "#f8fafc"; }}
                />
              </div>
              <div>
                <label style={lbl}>ИИН / БИН</label>
                <input style={inp} inputMode="numeric" placeholder="12 цифр" value={form.tax_id ?? ""} onChange={(e) => setField("tax_id", e.target.value.replace(/\D/g, "").slice(0, 12))}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "#0E1826"; e.currentTarget.style.background = "#fff"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "#E2E8EE"; e.currentTarget.style.background = "#f8fafc"; }}
                />
              </div>
              <div>
                <label style={lbl}>Страна (ISO) *</label>
                <input style={inp} required maxLength={2} placeholder="KZ" value={form.country} onChange={(e) => setField("country", e.target.value.toUpperCase())}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "#0E1826"; e.currentTarget.style.background = "#fff"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "#E2E8EE"; e.currentTarget.style.background = "#f8fafc"; }}
                />
              </div>
              <div>
                <label style={lbl}>Город *</label>
                <input style={inp} required placeholder="Алматы" value={form.city} onChange={(e) => setField("city", e.target.value)}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "#0E1826"; e.currentTarget.style.background = "#fff"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "#E2E8EE"; e.currentTarget.style.background = "#f8fafc"; }}
                />
              </div>
              <div>
                <label style={lbl}>Индекс</label>
                <input style={inp} placeholder="050000" value={form.postal_code ?? ""} onChange={(e) => setField("postal_code", e.target.value)}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "#0E1826"; e.currentTarget.style.background = "#fff"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "#E2E8EE"; e.currentTarget.style.background = "#f8fafc"; }}
                />
              </div>
              <div style={{ gridColumn: "1 / -1" }}>
                <label style={lbl}>Адрес, строка 1 *</label>
                <input style={inp} required placeholder="ул. Абая, д. 10, кв. 5" value={form.address_line1} onChange={(e) => setField("address_line1", e.target.value)}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "#0E1826"; e.currentTarget.style.background = "#fff"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "#E2E8EE"; e.currentTarget.style.background = "#f8fafc"; }}
                />
              </div>
              <div style={{ gridColumn: "1 / -1" }}>
                <label style={lbl}>Адрес, строка 2</label>
                <input style={inp} placeholder="Офис 301" value={form.address_line2 ?? ""} onChange={(e) => setField("address_line2", e.target.value)}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "#0E1826"; e.currentTarget.style.background = "#fff"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "#E2E8EE"; e.currentTarget.style.background = "#f8fafc"; }}
                />
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
              <input
                type="checkbox"
                id="isDefault"
                checked={form.is_default ?? false}
                onChange={(e) => setField("is_default", e.target.checked)}
                style={{ width: 16, height: 16, cursor: "pointer" }}
              />
              <label htmlFor="isDefault" style={{ fontSize: 14, color: "#475569", cursor: "pointer" }}>
                Использовать как адрес по умолчанию
              </label>
            </div>

            {formError && (
              <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, padding: "10px 14px", color: "#b91c1c", fontSize: 13, marginBottom: 16 }}>
                {formError}
              </div>
            )}

            <div style={{ display: "flex", gap: 10 }}>
              <button
                type="submit"
                disabled={saving}
                style={{ padding: "10px 24px", borderRadius: 10, border: "none", background: "#0E1826", color: "#fff", fontSize: 14, fontWeight: 600, cursor: saving ? "not-allowed" : "pointer", opacity: saving ? 0.7 : 1, fontFamily: "inherit" }}
              >
                {saving ? "Сохраняем…" : "Сохранить"}
              </button>
              <button
                type="button"
                onClick={() => { setShowForm(false); setForm(EMPTY); setFormError(null); }}
                style={{ padding: "10px 20px", borderRadius: 10, border: "1px solid #E2E8EE", background: "#fff", color: "#64748b", fontSize: 14, fontWeight: 500, cursor: "pointer", fontFamily: "inherit" }}
              >
                Отмена
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Address list */}
      {isLoading ? (
        <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, padding: 48, textAlign: "center", color: "#64748b", fontSize: 14 }}>
          Загружаем адреса…
        </div>
      ) : addresses.length === 0 ? (
        <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 16, padding: "64px 24px", textAlign: "center" }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>📍</div>
          <p style={{ fontSize: 16, fontWeight: 700, margin: "0 0 6px", color: "#0E1826" }}>
            Адресов пока нет
          </p>
          <p style={{ margin: "0 0 20px", fontSize: 14, color: "#64748b" }}>
            Сохраните часто используемые адреса для быстрого оформления заказов
          </p>
          <button
            onClick={() => setShowForm(true)}
            style={{ padding: "10px 24px", borderRadius: 10, border: "none", background: "#0E1826", color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
          >
            Добавить первый адрес
          </button>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(auto-fill, minmax(320px, 1fr))", gap: isMobile ? 12 : 16 }}>
          {addresses.map((addr) => {
            const isDeleting = deletingId === addr.id;
            const isConfirming = confirmDeleteId === addr.id;
            return (
              <div
                key={addr.id}
                style={{
                  background: "#fff",
                  border: isConfirming ? "1px solid #fca5a5" : "1px solid #E2E8EE",
                  borderRadius: 14,
                  padding: "20px 24px",
                  opacity: isDeleting ? 0.5 : 1,
                  transition: "opacity 0.15s",
                  position: "relative",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
                  <div>
                    {addr.label && (
                      <div style={{ fontSize: 12, fontWeight: 600, color: "#7c3aed", background: "#ede9fe", padding: "2px 8px", borderRadius: 999, display: "inline-block", marginBottom: 6 }}>
                        {addr.label}
                      </div>
                    )}
                    {addr.is_default && (
                      <div style={{ fontSize: 12, fontWeight: 600, color: "#166534", background: "#dcfce7", padding: "2px 8px", borderRadius: 999, display: "inline-block", marginBottom: 6, marginLeft: addr.label ? 6 : 0 }}>
                        По умолчанию
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => setConfirmDeleteId(isConfirming ? null : addr.id)}
                    disabled={isDeleting}
                    style={{ display: "flex", alignItems: "center", justifyContent: "center", width: 30, height: 30, borderRadius: 8, border: "1px solid #fecaca", background: "#fff", color: "#ef4444", cursor: isDeleting ? "not-allowed" : "pointer", padding: 0, flexShrink: 0 }}
                  >
                    <IconTrash />
                  </button>
                </div>

                <div style={{ fontSize: 15, fontWeight: 700, color: "#0E1826", marginBottom: 4 }}>
                  {addr.full_name}
                </div>
                <div style={{ fontSize: 13, color: "#475569", marginBottom: 2 }}>{addr.phone}</div>
                {addr.company_name && (
                  <div style={{ fontSize: 13, color: "#64748b", marginBottom: 4 }}>{addr.company_name}</div>
                )}
                <div style={{ fontSize: 13, color: "#64748b", marginTop: 8, lineHeight: 1.6 }}>
                  {addr.country}, {addr.city}{addr.postal_code ? ` ${addr.postal_code}` : ""}<br />
                  {addr.address_line1}
                  {addr.address_line2 && <>, {addr.address_line2}</>}
                </div>

                {isConfirming && (
                  <div style={{ marginTop: 14, padding: "10px 14px", background: "#fef2f2", borderRadius: 8, display: "flex", alignItems: "center", gap: 10, fontSize: 13 }}>
                    <span style={{ flex: 1, color: "#7f1d1d" }}>Удалить адрес?</span>
                    <button onClick={() => void handleDelete(addr.id)} style={{ padding: "5px 12px", borderRadius: 7, border: "none", background: "#ef4444", color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
                      Да
                    </button>
                    <button onClick={() => setConfirmDeleteId(null)} style={{ padding: "5px 12px", borderRadius: 7, border: "1px solid #fca5a5", background: "#fff", color: "#b91c1c", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
                      Нет
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
