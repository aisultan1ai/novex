"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import {
  createAdminUser,
  listAdminUsers,
  updateAdminUser,
  type AdminUserCreatePayload,
} from "@/lib/api/admin";
import type { AdminUser } from "@/types/admin";

const ROLE_LABELS: Record<string, string> = {
  customer: "Клиент",
  operator: "Оператор",
  admin:    "Админ",
  carrier:  "Перевозчик",
};

const ROLE_STYLES: Record<string, { bg: string; color: string }> = {
  admin:    { bg: "#fef3c7", color: "#92400e" },
  operator: { bg: "#ede9fe", color: "#5b21b6" },
  carrier:  { bg: "#dbeafe", color: "#1e40af" },
  customer: { bg: "#f1f5f9", color: "#475569" },
};

const EMPTY_FORM: AdminUserCreatePayload = {
  email: "", password: "", full_name: "", phone: "", role: "customer",
};

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  // Create user modal
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<AdminUserCreatePayload>(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  const SIZE = 20;

  const load = useCallback(() => {
    setIsLoading(true);
    listAdminUsers({ page, size: SIZE, search: search || undefined })
      .then((res) => { setUsers(res.items); setTotal(res.total); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, [page, search]);

  useEffect(() => { void load(); }, [load]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  }

  async function toggleActive(user: AdminUser) {
    setTogglingId(user.id);
    try {
      await updateAdminUser(user.id, { is_active: !user.is_active });
      void load();
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setTogglingId(null);
    }
  }

  function openCreate() {
    setForm(EMPTY_FORM);
    setCreateError(null);
    setShowPassword(false);
    setShowCreate(true);
  }

  async function handleCreate() {
    setCreateError(null);
    if (!form.email.trim()) { setCreateError("Укажите email"); return; }
    if (!form.password.trim()) { setCreateError("Укажите пароль"); return; }
    if (form.password.length < 6) { setCreateError("Пароль минимум 6 символов"); return; }
    setCreating(true);
    try {
      await createAdminUser({
        ...form,
        full_name: form.full_name?.trim() || undefined,
        phone:     form.phone?.trim() || undefined,
      });
      setShowCreate(false);
      void load();
    } catch (e: unknown) {
      setCreateError(e instanceof Error ? e.message : "Ошибка создания");
    } finally {
      setCreating(false);
    }
  }

  const totalPages = Math.ceil(total / SIZE);

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0f172a" }}>Пользователи</h2>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>Все аккаунты · {total} всего</p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <button
            onClick={openCreate}
            style={{ padding: "10px 18px", borderRadius: 10, border: "none", background: "#0f172a", color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", display: "flex", alignItems: "center", gap: 6 }}
          >
            + Добавить
          </button>
          <form onSubmit={handleSearch} style={{ display: "flex", gap: 8 }}>
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Поиск по email / имени..."
              style={{ padding: "10px 14px", borderRadius: 10, border: "1px solid #e5e7eb", fontSize: 14, width: 240, fontFamily: "inherit", outline: "none", background: "#ffffff", color: "#0f172a" }}
            />
            <button type="submit" style={{ padding: "10px 18px", borderRadius: 10, border: "none", background: "#f1f5f9", color: "#0f172a", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
              Найти
            </button>
          </form>
        </div>
      </div>

      {error && (
        <div style={{ padding: "12px 16px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 14, marginBottom: 20 }}>
          {error}
        </div>
      )}

      <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "60px 1fr 140px 100px 80px 100px 80px", gap: 12, padding: "12px 20px", background: "#f8fafc", borderBottom: "1px solid #e5e7eb", fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          <span>ID</span>
          <span>Пользователь</span>
          <span>Тип</span>
          <span>Роль</span>
          <span>Заказы</span>
          <span>Статус</span>
          <span>Действие</span>
        </div>

        {isLoading ? (
          <div style={{ padding: 48, textAlign: "center", color: "#64748b", fontSize: 14 }}>Загружаем…</div>
        ) : users.length === 0 ? (
          <div style={{ padding: 48, textAlign: "center", color: "#94a3b8", fontSize: 14 }}>Пользователей не найдено</div>
        ) : (
          users.map((user, idx) => {
            const roleStyle = ROLE_STYLES[user.role ?? "customer"] ?? ROLE_STYLES.customer;
            return (
              <div
                key={user.id}
                style={{ display: "grid", gridTemplateColumns: "60px 1fr 140px 100px 80px 100px 80px", gap: 12, padding: "14px 20px", borderBottom: idx < users.length - 1 ? "1px solid #f1f5f9" : "none", alignItems: "center" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "#f8fafc"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = ""; }}
              >
                <span style={{ fontFamily: "monospace", fontSize: 13, color: "#94a3b8", fontWeight: 600 }}>#{user.id}</span>

                <div style={{ minWidth: 0 }}>
                  <Link href={`/dashboard/admin/users/${user.id}`} style={{ fontSize: 14, fontWeight: 600, color: "#0f172a", textDecoration: "none" }}>
                    {user.full_name || user.email}
                  </Link>
                  {user.full_name && (
                    <div style={{ fontSize: 12, color: "#94a3b8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{user.email}</div>
                  )}
                </div>

                <div style={{ fontSize: 13, color: "#64748b" }}>
                  {user.customer_type === "company"
                    ? `Компания${user.company_name ? ` · ${user.company_name}` : ""}`
                    : "Физ. лицо"}
                </div>

                <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 11, fontWeight: 700, background: roleStyle.bg, color: roleStyle.color, width: "fit-content" }}>
                  {ROLE_LABELS[user.role ?? "customer"] ?? user.role}
                </span>

                <span style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>{user.order_count}</span>

                <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: user.is_active ? "#dcfce7" : "#f1f5f9", color: user.is_active ? "#166534" : "#94a3b8" }}>
                  {user.is_active ? "Активен" : "Заблок."}
                </span>

                <button
                  onClick={() => void toggleActive(user)}
                  disabled={togglingId === user.id}
                  style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #e5e7eb", background: "#ffffff", color: user.is_active ? "#b91c1c" : "#16a34a", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", opacity: togglingId === user.id ? 0.5 : 1 }}
                >
                  {user.is_active ? "Блок." : "Разблок."}
                </button>
              </div>
            );
          })
        )}
      </div>

      {totalPages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 24 }}>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <button
              key={p} onClick={() => setPage(p)}
              style={{ width: 36, height: 36, borderRadius: 8, border: "1px solid #e5e7eb", background: p === page ? "#0f172a" : "#ffffff", color: p === page ? "#ffffff" : "#0f172a", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
            >
              {p}
            </button>
          ))}
        </div>
      )}

      {/* ── Create user modal ────────────────────────────────── */}
      {showCreate && (
        <div
          onClick={(e) => { if (e.target === e.currentTarget) setShowCreate(false); }}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center" }}
        >
          <div style={{ background: "#fff", borderRadius: 20, padding: "36px 40px", width: 440, boxShadow: "0 24px 64px rgba(0,0,0,0.16)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 26 }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "#0f172a" }}>Новый пользователь</h2>
                <p style={{ margin: "4px 0 0", fontSize: 13, color: "#94a3b8" }}>Создать аккаунт вручную</p>
              </div>
              <button
                onClick={() => setShowCreate(false)}
                style={{ width: 32, height: 32, borderRadius: 8, border: "1px solid #e5e7eb", background: "#fff", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "#64748b", fontSize: 18, fontFamily: "inherit" }}
              >×</button>
            </div>

            {/* Role selector - at the top so it's prominent */}
            <div style={{ marginBottom: 18 }}>
              <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
                Роль
              </label>
              <div style={{ display: "flex", gap: 8 }}>
                {(["customer", "operator", "admin"] as const).map((r) => {
                  // «Перевозчик» намеренно не в списке — учётка сотрудника
                  // перевозчика привязывается к carrier_id и создаётся из
                  // раздела «Перевозчики» → детали → «+ Добавить аккаунт».
                  const s = ROLE_STYLES[r];
                  const active = form.role === r;
                  return (
                    <button
                      key={r}
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, role: r }))}
                      style={{
                        flex: 1,
                        padding: "9px 0",
                        borderRadius: 10,
                        border: active ? `2px solid ${s.color}` : "2px solid #e5e7eb",
                        background: active ? s.bg : "#fff",
                        color: active ? s.color : "#94a3b8",
                        fontSize: 13,
                        fontWeight: 700,
                        cursor: "pointer",
                        fontFamily: "inherit",
                        transition: "all 0.15s",
                      }}
                    >
                      {ROLE_LABELS[r]}
                    </button>
                  );
                })}
              </div>
              <div style={{ marginTop: 8, fontSize: 11, color: "#94a3b8", lineHeight: 1.5 }}>
                Сотрудника перевозчика создавайте в{" "}
                <Link href="/dashboard/admin/carriers" style={{ color: "#4338ca", textDecoration: "underline" }}>
                  разделе «Перевозчики»
                </Link>
                {" "}→ откройте нужного перевозчика → «+ Добавить аккаунт».
              </div>
            </div>

            <div style={{ borderTop: "1px solid #f1f5f9", marginBottom: 18 }} />

            {/* Full name */}
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                Имя
              </label>
              <input
                value={form.full_name ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
                placeholder="Иван Иванов"
                style={{ width: "100%", padding: "10px 14px", borderRadius: 10, border: "1px solid #e5e7eb", fontSize: 14, boxSizing: "border-box", fontFamily: "inherit", outline: "none" }}
              />
            </div>

            {/* Email */}
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                Email <span style={{ color: "#dc2626" }}>*</span>
              </label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                placeholder="user@example.com"
                style={{ width: "100%", padding: "10px 14px", borderRadius: 10, border: "1px solid #e5e7eb", fontSize: 14, boxSizing: "border-box", fontFamily: "inherit", outline: "none" }}
              />
            </div>

            {/* Phone */}
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                Телефон
              </label>
              <input
                type="tel"
                value={form.phone ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                placeholder="+7 700 000 00 00"
                style={{ width: "100%", padding: "10px 14px", borderRadius: 10, border: "1px solid #e5e7eb", fontSize: 14, boxSizing: "border-box", fontFamily: "inherit", outline: "none" }}
              />
            </div>

            {/* Password */}
            <div style={{ marginBottom: 22 }}>
              <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                Пароль <span style={{ color: "#dc2626" }}>*</span>
              </label>
              <div style={{ display: "flex", alignItems: "center", border: "1px solid #e5e7eb", borderRadius: 10, overflow: "hidden", background: "#fff" }}>
                <input
                  type={showPassword ? "text" : "password"}
                  value={form.password}
                  onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                  placeholder="Минимум 6 символов"
                  style={{ flex: 1, border: "none", background: "transparent", padding: "10px 14px", fontSize: 14, outline: "none", fontFamily: "inherit" }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  style={{ padding: "0 14px", background: "none", border: "none", cursor: "pointer", color: "#94a3b8", fontSize: 13, fontFamily: "inherit" }}
                >
                  {showPassword ? "Скрыть" : "Показать"}
                </button>
              </div>
            </div>

            {createError && (
              <div style={{ color: "#b91c1c", fontSize: 13, marginBottom: 14, padding: "10px 14px", background: "#fef2f2", borderRadius: 8 }}>
                {createError}
              </div>
            )}

            <div style={{ display: "flex", gap: 10 }}>
              <button
                onClick={() => void handleCreate()}
                disabled={creating}
                style={{ flex: 1, padding: 12, borderRadius: 10, border: "none", background: "#0f172a", color: "#fff", fontSize: 14, fontWeight: 600, cursor: creating ? "not-allowed" : "pointer", opacity: creating ? 0.6 : 1, fontFamily: "inherit" }}
              >
                {creating ? "Создаём..." : "Создать пользователя"}
              </button>
              <button
                onClick={() => setShowCreate(false)}
                style={{ padding: "12px 20px", borderRadius: 10, border: "1px solid #e5e7eb", background: "#fff", color: "#475569", fontSize: 14, fontWeight: 500, cursor: "pointer", fontFamily: "inherit" }}
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
