"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { listAdminUsers, updateAdminUser } from "@/lib/api/admin";
import type { AdminUser } from "@/types/admin";

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<number | null>(null);

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

  const totalPages = Math.ceil(total / SIZE);

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0f172a" }}>Пользователи</h2>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>Все аккаунты · {total} всего</p>
        </div>
        <form onSubmit={handleSearch} style={{ display: "flex", gap: 8 }}>
          <input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Поиск по email / имени..."
            style={{ padding: "10px 14px", borderRadius: 10, border: "1px solid #e5e7eb", fontSize: 14, width: 260, fontFamily: "inherit", outline: "none", background: "#ffffff", color: "#0f172a" }}
          />
          <button type="submit" style={{ padding: "10px 20px", borderRadius: 10, border: "none", background: "#0f172a", color: "#ffffff", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
            Найти
          </button>
        </form>
      </div>

      {error && <div style={{ padding: "12px 16px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 14, marginBottom: 20 }}>{error}</div>}

      <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "60px 1fr 140px 80px 80px 100px 80px", gap: 12, padding: "12px 20px", background: "#f8fafc", borderBottom: "1px solid #e5e7eb", fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
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
          users.map((user, idx) => (
            <div
              key={user.id}
              style={{ display: "grid", gridTemplateColumns: "60px 1fr 140px 80px 80px 100px 80px", gap: 12, padding: "14px 20px", borderBottom: idx < users.length - 1 ? "1px solid #f1f5f9" : "none", alignItems: "center" }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "#f8fafc"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = ""; }}
            >
              <span style={{ fontFamily: "monospace", fontSize: 13, color: "#94a3b8", fontWeight: 600 }}>#{user.id}</span>

              <div style={{ minWidth: 0 }}>
                <Link href={`/dashboard/admin/users/${user.id}`} style={{ fontSize: 14, fontWeight: 600, color: "#0f172a", textDecoration: "none" }}>
                  {user.full_name || user.email}
                </Link>
                {user.full_name && <div style={{ fontSize: 12, color: "#94a3b8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{user.email}</div>}
              </div>

              <div style={{ fontSize: 13, color: "#64748b" }}>
                {user.customer_type === "company" ? `Компания${user.company_name ? ` · ${user.company_name}` : ""}` : "Физ. лицо"}
              </div>

              <span style={{ padding: "3px 8px", borderRadius: 999, fontSize: 11, fontWeight: 600, background: user.role === "admin" ? "#fef3c7" : "#f1f5f9", color: user.role === "admin" ? "#92400e" : "#475569" }}>
                {user.role}
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
          ))
        )}
      </div>

      {totalPages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 24 }}>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <button key={p} onClick={() => setPage(p)} style={{ width: 36, height: 36, borderRadius: 8, border: "1px solid #e5e7eb", background: p === page ? "#0f172a" : "#ffffff", color: p === page ? "#ffffff" : "#0f172a", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
              {p}
            </button>
          ))}
        </div>
      )}
    </>
  );
}
