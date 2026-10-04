"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  createCarrierAccount,
  getAdminCarrier,
  listCarrierAccounts,
  updateAdminCarrier,
  type CarrierAccount,
} from "@/lib/api/admin";
import type { AdminCarrierDetail } from "@/types/admin";
import { useIsAdmin } from "@/hooks/use-is-admin";

const inp: React.CSSProperties = {
  border: "1px solid #E2E8EE", borderRadius: 8, padding: "8px 12px",
  fontSize: 13, width: "100%", boxSizing: "border-box",
  fontFamily: "inherit", outline: "none", background: "#f8fafc", color: "#0B2545",
};
const lbl: React.CSSProperties = {
  display: "block", fontSize: 12, fontWeight: 600, color: "#64748b",
  marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.04em",
};

const EMPTY_ACCOUNT = { email: "", full_name: "", temp_password: "" };

export default function AdminCarrierOverviewPage() {
  const isAdmin = useIsAdmin();
  const { id } = useParams<{ id: string }>();
  const carrierId = Number(id);

  const [carrier, setCarrier] = useState<AdminCarrierDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({ name: "", description: "", is_active: true, notification_email: "" });
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<{ text: string; ok: boolean } | null>(null);

  const [showAccountForm, setShowAccountForm] = useState(false);
  const [accountForm, setAccountForm] = useState(EMPTY_ACCOUNT);
  const [savingAccount, setSavingAccount] = useState(false);
  const [accountMsg, setAccountMsg] = useState<{ text: string; ok: boolean } | null>(null);
  const [accounts, setAccounts] = useState<CarrierAccount[] | null>(null);

  function loadAccounts() {
    listCarrierAccounts(carrierId)
      .then(setAccounts)
      .catch(() => setAccounts([]));
  }

  function load() {
    setLoading(true);
    getAdminCarrier(carrierId)
      .then((c) => {
        setCarrier(c);
        setForm({
          name: c.name,
          description: c.description ?? "",
          is_active: c.is_active,
          notification_email: c.notification_email ?? "",
        });
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); loadAccounts(); }, [carrierId]); // eslint-disable-line

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaveMsg(null);
    setSaving(true);
    try {
      await updateAdminCarrier(carrierId, {
        name: form.name,
        description: form.description || undefined,
        is_active: form.is_active,
        // Пустая строка = очистить; строка с email = задать. Всегда шлём
        // явное значение, иначе backend не отличит «не менять» от «очистить».
        notification_email: form.notification_email.trim(),
      });
      setSaveMsg({ text: "Сохранено", ok: true });
      load();
    } catch (err: unknown) {
      setSaveMsg({ text: (err as Error).message, ok: false });
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateAccount(e: React.FormEvent) {
    e.preventDefault();
    setAccountMsg(null);
    setSavingAccount(true);
    try {
      await createCarrierAccount(carrierId, {
        email: accountForm.email.trim(),
        full_name: accountForm.full_name.trim() || undefined,
        temp_password: accountForm.temp_password,
      });
      setAccountMsg({ text: "Аккаунт создан", ok: true });
      setAccountForm(EMPTY_ACCOUNT);
      setShowAccountForm(false);
      loadAccounts();
    } catch (err: unknown) {
      setAccountMsg({ text: (err as Error).message, ok: false });
    } finally {
      setSavingAccount(false);
    }
  }

  if (loading) return <div style={{ padding: 40, color: "#64748b" }}>Загружаем…</div>;
  if (error) return <div style={{ padding: "12px 16px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c" }}>{error}</div>;
  if (!carrier) return null;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 20, alignItems: "start" }}>
      {/* Edit form */}
      <form onSubmit={handleSave} style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 14, padding: "24px" }}>
<fieldset disabled={!isAdmin} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: "#0B2545", marginBottom: 18 }}>Основные данные</div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 }}>
          <div>
            <label style={lbl}>Название</label>
            <input style={inp} value={form.name} onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} required />
          </div>
          <div>
            <label style={lbl}>Код</label>
            <input style={{ ...inp, background: "#f1f5f9", color: "#94a3b8" }} value={carrier.code} readOnly />
          </div>
          <div style={{ gridColumn: "1 / -1" }}>
            <label style={lbl}>Описание</label>
            <input style={inp} value={form.description} onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Необязательно" />
          </div>
          <div style={{ gridColumn: "1 / -1" }}>
            <label style={lbl}>Email для уведомлений об отменах</label>
            <input
              style={inp}
              type="email"
              value={form.notification_email}
              onChange={(e) => setForm(f => ({ ...f, notification_email: e.target.value }))}
              placeholder="ops@carrier.example - необязательно"
            />
            <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 6 }}>
              На этот адрес будем присылать заявки на отмену от клиентов. Оставьте пустым, если не нужно.
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
          <input
            type="checkbox"
            id="is_active"
            checked={form.is_active}
            onChange={(e) => setForm(f => ({ ...f, is_active: e.target.checked }))}
            style={{ width: 16, height: 16, cursor: "pointer" }}
          />
          <label htmlFor="is_active" style={{ fontSize: 13, cursor: "pointer", color: "#0B2545" }}>
            Перевозчик активен (доступен для котировок)
          </label>
        </div>

        {saveMsg && (
          <div style={{ padding: "10px 14px", borderRadius: 8, marginBottom: 14, fontSize: 13, background: saveMsg.ok ? "#f0fdf4" : "#fef2f2", color: saveMsg.ok ? "#166534" : "#b91c1c" }}>
            {saveMsg.text}
          </div>
        )}

        <button type="submit" disabled={saving} style={{ padding: "10px 24px", borderRadius: 10, border: "none", background: "#0B2545", color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
          {saving ? "Сохраняем…" : "Сохранить"}
        </button>
      </fieldset>
</form>

      {/* Account section */}
      <div style={{ background: "#fff", border: "1px solid #E2E8EE", borderRadius: 14, padding: "22px 24px" }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: "#0B2545", marginBottom: 6 }}>Аккаунт перевозчика</div>
        <p style={{ fontSize: 13, color: "#64748b", marginTop: 0, marginBottom: 16 }}>
          {accounts && accounts.length > 0
            ? "Сотрудники этого перевозчика, у которых есть доступ в личный кабинет."
            : "Создайте учётную запись, чтобы перевозчик мог войти в личный кабинет и управлять заказами."}
        </p>

        {accountMsg && (
          <div style={{ padding: "10px 14px", borderRadius: 8, marginBottom: 14, fontSize: 13, background: accountMsg.ok ? "#f0fdf4" : "#fef2f2", color: accountMsg.ok ? "#166534" : "#b91c1c" }}>
            {accountMsg.text}
          </div>
        )}

        {accounts && accounts.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 14 }}>
            {accounts.map((a) => (
              <Link
                key={a.id}
                href={`/dashboard/admin/users/${a.id}`}
                style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, padding: "10px 12px", background: "#f8fafc", border: "1px solid #E2E8EE", borderRadius: 10, textDecoration: "none", cursor: "pointer", transition: "background 0.15s" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "#f1f5f9"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "#f8fafc"; }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#0B2545", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {a.full_name || a.email}
                  </div>
                  {a.full_name && (
                    <div style={{ fontSize: 11, color: "#94a3b8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {a.email}
                    </div>
                  )}
                </div>
                <span
                  style={{
                    fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 999,
                    background: a.is_active ? "#dcfce7" : "#f1f5f9",
                    color: a.is_active ? "#166534" : "#94a3b8",
                    flexShrink: 0,
                  }}
                >
                  {a.is_active ? "Активен" : "Заблок."}
                </span>
              </Link>
            ))}
          </div>
        )}

        {!isAdmin ? null : !showAccountForm ? (
          <button
            onClick={() => setShowAccountForm(true)}
            style={{ padding: "9px 18px", borderRadius: 10, border: "1px solid #c7d2fe", background: "#eef2ff", color: "#4338ca", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
          >
            {accounts && accounts.length > 0 ? "+ Добавить ещё аккаунт" : "+ Создать аккаунт"}
          </button>
        ) : (
          <form onSubmit={handleCreateAccount} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label style={lbl}>Email</label>
              <input style={inp} type="email" required value={accountForm.email} onChange={(e) => setAccountForm(f => ({ ...f, email: e.target.value }))} placeholder="carrier@example.com" />
            </div>
            <div>
              <label style={lbl}>Имя (необязательно)</label>
              <input style={inp} value={accountForm.full_name} onChange={(e) => setAccountForm(f => ({ ...f, full_name: e.target.value }))} />
            </div>
            <div>
              <label style={lbl}>Временный пароль</label>
              <input style={inp} required minLength={8} value={accountForm.temp_password} onChange={(e) => setAccountForm(f => ({ ...f, temp_password: e.target.value }))} placeholder="Минимум 8 символов" />
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button type="submit" disabled={savingAccount} style={{ padding: "9px 18px", borderRadius: 10, border: "none", background: "#0B2545", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
                {savingAccount ? "…" : "Создать"}
              </button>
              <button type="button" onClick={() => setShowAccountForm(false)} style={{ padding: "9px 14px", borderRadius: 10, border: "1px solid #E2E8EE", background: "#fff", color: "#64748b", fontSize: 13, cursor: "pointer", fontFamily: "inherit" }}>
                Отмена
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
