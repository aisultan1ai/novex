"use client";

import { useCallback, useEffect, useState } from "react";

import { listAuditLogs, type AuditLogItem } from "@/lib/api/admin";

const ACTION_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  "payment.approve":      { label: "Оплата подтверждена",        color: "#15803d", bg: "#f0fdf4" },
  "payment.reject":       { label: "Оплата отклонена",           color: "#b91c1c", bg: "#fef2f2" },
  "order.status_change":  { label: "Статус заказа изменён",      color: "#1d4ed8", bg: "#eff6ff" },
  "order.retry_dispatch": { label: "Повторная отправка",         color: "#7c3aed", bg: "#f5f3ff" },
  "order.mark_dispatched":{ label: "Отмечен как отправленный",   color: "#0369a1", bg: "#f0f9ff" },
  "user.create":          { label: "Пользователь создан",        color: "#0f172a", bg: "#f8fafc" },
  "user.update":          { label: "Пользователь обновлён",      color: "#475569", bg: "#f8fafc" },
  "settings.update":      { label: "Настройки изменены",         color: "#92400e", bg: "#fffbeb" },
};

const RESOURCE_LABELS: Record<string, string> = {
  payment:  "Платёж",
  order:    "Заказ",
  user:     "Пользователь",
  settings: "Настройки",
};

const ALL_ACTIONS = Object.keys(ACTION_LABELS);
const ALL_RESOURCE_TYPES = Object.keys(RESOURCE_LABELS);

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function parseJson(val: string | null): Record<string, unknown> | null {
  if (!val) return null;
  try { return JSON.parse(val) as Record<string, unknown>; } catch { return null; }
}

function ValueDiff({ old_value, new_value }: { old_value: string | null; new_value: string | null }) {
  const oldObj = parseJson(old_value);
  const newObj = parseJson(new_value);

  if (!oldObj && !newObj) return <span style={{ color: "#94a3b8", fontSize: 12 }}>—</span>;

  const keys = Array.from(new Set([...Object.keys(oldObj ?? {}), ...Object.keys(newObj ?? {})]));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {keys.map((key) => {
        const oldVal = oldObj?.[key];
        const newVal = newObj?.[key];
        const changed = JSON.stringify(oldVal) !== JSON.stringify(newVal);

        return (
          <div key={key} style={{ fontSize: 12, display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ color: "#94a3b8", fontWeight: 600, minWidth: 60 }}>{key}:</span>
            {oldVal !== undefined && changed && (
              <span style={{
                background: "#fef2f2", color: "#b91c1c", padding: "1px 7px",
                borderRadius: 5, fontFamily: "monospace", fontSize: 11,
                textDecoration: "line-through", opacity: 0.7,
              }}>
                {String(oldVal)}
              </span>
            )}
            {newVal !== undefined && (
              <span style={{
                background: changed ? "#f0fdf4" : "#f8fafc",
                color: changed ? "#15803d" : "#475569",
                padding: "1px 7px", borderRadius: 5,
                fontFamily: "monospace", fontSize: 11,
              }}>
                {String(newVal)}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ActionBadge({ action }: { action: string }) {
  const meta = ACTION_LABELS[action] ?? { label: action, color: "#475569", bg: "#f1f5f9" };
  return (
    <span style={{
      display: "inline-block",
      background: meta.bg,
      color: meta.color,
      fontSize: 11,
      fontWeight: 700,
      padding: "3px 10px",
      borderRadius: 20,
      whiteSpace: "nowrap",
    }}>
      {meta.label}
    </span>
  );
}

export default function AdminAuditLogsPage() {
  const [items, setItems] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filterAction, setFilterAction] = useState("");
  const [filterResource, setFilterResource] = useState("");

  const SIZE = 50;

  const load = useCallback(() => {
    setIsLoading(true);
    setError(null);
    listAuditLogs({
      page,
      size: SIZE,
      action: filterAction || undefined,
      resource_type: filterResource || undefined,
    })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
        setPages(res.pages);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, [page, filterAction, filterResource]);

  useEffect(() => { load(); }, [load]);

  function handleFilterChange() {
    setPage(1);
  }

  return (
    <>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0f172a" }}>Журнал действий</h2>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>
            {total > 0 ? `${total} записей` : "Записи действий администраторов"}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap" }}>
        <select
          value={filterAction}
          onChange={(e) => { setFilterAction(e.target.value); handleFilterChange(); }}
          style={{
            padding: "8px 14px", borderRadius: 10, border: "1px solid #e5e7eb",
            background: "#fff", fontSize: 13, color: "#0f172a", fontFamily: "inherit", cursor: "pointer",
          }}
        >
          <option value="">Все действия</option>
          {ALL_ACTIONS.map((a) => (
            <option key={a} value={a}>{ACTION_LABELS[a]?.label ?? a}</option>
          ))}
        </select>

        <select
          value={filterResource}
          onChange={(e) => { setFilterResource(e.target.value); handleFilterChange(); }}
          style={{
            padding: "8px 14px", borderRadius: 10, border: "1px solid #e5e7eb",
            background: "#fff", fontSize: 13, color: "#0f172a", fontFamily: "inherit", cursor: "pointer",
          }}
        >
          <option value="">Все ресурсы</option>
          {ALL_RESOURCE_TYPES.map((r) => (
            <option key={r} value={r}>{RESOURCE_LABELS[r] ?? r}</option>
          ))}
        </select>

        {(filterAction || filterResource) && (
          <button
            onClick={() => { setFilterAction(""); setFilterResource(""); handleFilterChange(); }}
            style={{
              padding: "8px 14px", borderRadius: 10, border: "1px solid #e5e7eb",
              background: "#fff", fontSize: 13, color: "#64748b", cursor: "pointer", fontFamily: "inherit",
            }}
          >
            Сбросить
          </button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 10, padding: "12px 16px", color: "#b91c1c", fontSize: 14, marginBottom: 20 }}>
          {error}
        </div>
      )}

      {/* Table */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "hidden" }}>
        {/* Header */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "150px 180px 200px 110px 80px 1fr",
          gap: 12, padding: "12px 24px",
          background: "#f8fafc", borderBottom: "1px solid #e5e7eb",
          fontSize: 11, fontWeight: 700, color: "#94a3b8",
          textTransform: "uppercase", letterSpacing: "0.05em",
        }}>
          <span>Дата</span>
          <span>Администратор</span>
          <span>Действие</span>
          <span>Ресурс</span>
          <span>ID</span>
          <span>Изменения</span>
        </div>

        {isLoading ? (
          <div style={{ padding: 48, textAlign: "center", color: "#64748b", fontSize: 14 }}>
            Загружаем журнал…
          </div>
        ) : items.length === 0 ? (
          <div style={{ padding: "64px 24px", textAlign: "center" }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>📋</div>
            <p style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#0f172a" }}>Записей нет</p>
            <p style={{ margin: "6px 0 0", fontSize: 14, color: "#64748b" }}>
              {filterAction || filterResource ? "Попробуйте сбросить фильтры" : "Журнал будет пополняться по мере действий администраторов"}
            </p>
          </div>
        ) : (
          items.map((log, idx) => (
            <div
              key={log.id}
              style={{
                display: "grid",
                gridTemplateColumns: "150px 180px 200px 110px 80px 1fr",
                gap: 12, padding: "14px 24px",
                borderBottom: idx === items.length - 1 ? "none" : "1px solid #f1f5f9",
                alignItems: "start",
              }}
            >
              <div style={{ fontSize: 12, color: "#64748b", whiteSpace: "nowrap" }}>
                {formatDateTime(log.created_at)}
              </div>

              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#0f172a" }}>
                  {log.actor_email}
                </div>
                {log.actor_id && (
                  <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>
                    ID {log.actor_id}
                  </div>
                )}
              </div>

              <div>
                <ActionBadge action={log.action} />
              </div>

              <div style={{ fontSize: 13, color: "#475569" }}>
                {RESOURCE_LABELS[log.resource_type] ?? log.resource_type}
              </div>

              <div style={{ fontSize: 12, fontFamily: "monospace", color: "#94a3b8" }}>
                {log.resource_id != null ? `#${log.resource_id}` : "—"}
              </div>

              <div>
                <ValueDiff old_value={log.old_value} new_value={log.new_value} />
              </div>
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 8, marginTop: 20 }}>
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
            style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid #e5e7eb", background: "#fff", color: "#475569", fontSize: 13, fontWeight: 500, cursor: page === pages ? "not-needed" : "pointer", opacity: page === pages ? 0.4 : 1, fontFamily: "inherit" }}
          >
            Вперёд →
          </button>
        </div>
      )}
    </>
  );
}
