"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  adminApproveCancellation,
  adminListCancellations,
  adminRejectCancellation,
  adminRetryApiCancellation,
  type CancellationRequestFull,
  type CancellationStatus,
} from "@/lib/api/cancellations";

const STATUS_LABELS: Record<CancellationStatus, string> = {
  pending: "Ожидает",
  approved: "Подтверждено",
  api_cancelled: "Отменено через API",
  rejected: "Отклонено",
};

const STATUS_COLORS: Record<CancellationStatus, { bg: string; color: string }> = {
  pending:       { bg: "#fef3c7", color: "#92400e" },
  approved:      { bg: "#dcfce7", color: "#166534" },
  api_cancelled: { bg: "#dbeafe", color: "#1e40af" },
  rejected:      { bg: "#fee2e2", color: "#991b1b" },
};

// Карrier'ы с API отмены - только для них имеет смысл кнопка «Повторить API».
const API_CARRIERS = new Set(["cse", "exline"]);

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("ru-KZ", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function StatusBadge({ status }: { status: CancellationStatus }) {
  const { bg, color } = STATUS_COLORS[status];
  return (
    <span style={{ display: "inline-block", padding: "3px 10px", borderRadius: 999, background: bg, color, fontSize: 12, fontWeight: 700 }}>
      {STATUS_LABELS[status]}
    </span>
  );
}

export default function AdminCancellationRequestsPage() {
  const [items, setItems] = useState<CancellationRequestFull[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<CancellationStatus | "all">("pending");
  const [carrierFilter, setCarrierFilter] = useState<string>("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await adminListCancellations({
        status: statusFilter === "all" ? undefined : statusFilter,
        carrier_code: carrierFilter || undefined,
        page,
        size: 20,
      });
      setItems(resp.items);
      setTotal(resp.total);
      setPages(resp.pages);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить заявки");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, carrierFilter, page]);

  useEffect(() => { void load(); }, [load]);

  // При смене фильтра сбрасываем страницу - иначе можно улететь на пустую.
  useEffect(() => { setPage(1); }, [statusFilter, carrierFilter]);

  const selected = useMemo(
    () => items.find((r) => r.id === selectedId) ?? null,
    [items, selectedId],
  );

  async function handleApprove(id: number) {
    if (!window.confirm("Подтвердить отмену? Заказ будет переведён в статус «Отменён», комиссия сторнируется, платежи - в refund_pending.")) return;
    setBusyId(id);
    try {
      await adminApproveCancellation(id);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setBusyId(null);
    }
  }

  async function handleReject(id: number) {
    const comment = window.prompt("Причина отклонения заявки (обязательно, минимум 3 символа):");
    if (!comment || comment.trim().length < 3) return;
    setBusyId(id);
    try {
      await adminRejectCancellation(id, comment.trim());
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setBusyId(null);
    }
  }

  async function handleRetry(id: number) {
    setBusyId(id);
    try {
      await adminRetryApiCancellation(id);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: 4, background: "#fff", border: "1px solid #e5e7eb", borderRadius: 10, padding: 3 }}>
          {(["pending", "approved", "api_cancelled", "rejected", "all"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              style={{
                padding: "6px 14px", borderRadius: 8, border: "none",
                background: statusFilter === s ? "#0f172a" : "transparent",
                color: statusFilter === s ? "#fff" : "#64748b",
                fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
              }}
            >
              {s === "all" ? "Все" : STATUS_LABELS[s]}
            </button>
          ))}
        </div>
        <input
          value={carrierFilter}
          onChange={(e) => setCarrierFilter(e.target.value)}
          placeholder="Фильтр по carrier_code (azimuth / cse / exline)"
          style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 13, minWidth: 280, fontFamily: "inherit", outline: "none" }}
        />
        <div style={{ fontSize: 12, color: "#94a3b8", marginLeft: "auto" }}>{total} шт.</div>
      </div>

      {error && (
        <div style={{ padding: "12px 16px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 13 }}>
          {error}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 16, alignItems: "start" }}>
        {/* List */}
        <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, overflow: "hidden" }}>
          <div style={{ display: "grid", gridTemplateColumns: "70px 90px 100px 1fr 140px 140px", gap: 12, padding: "10px 20px", background: "#f8fafc", borderBottom: "1px solid #e5e7eb", fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            <span>ID</span>
            <span>Заказ</span>
            <span>Перевозчик</span>
            <span>Причина</span>
            <span>Статус</span>
            <span>Дата</span>
          </div>
          {loading ? (
            <div style={{ padding: 40, textAlign: "center", color: "#64748b", fontSize: 14 }}>Загружаем…</div>
          ) : items.length === 0 ? (
            <div style={{ padding: "40px 20px", textAlign: "center", color: "#64748b", fontSize: 14 }}>Заявок с такими фильтрами нет</div>
          ) : (
            items.map((r) => (
              <div
                key={r.id}
                onClick={() => setSelectedId(r.id)}
                style={{
                  display: "grid", gridTemplateColumns: "70px 90px 100px 1fr 140px 140px", gap: 12,
                  padding: "12px 20px", borderBottom: "1px solid #f1f5f9", alignItems: "center",
                  fontSize: 13, cursor: "pointer",
                  background: selectedId === r.id ? "#eff6ff" : "transparent",
                }}
              >
                <span style={{ fontFamily: "monospace", color: "#94a3b8" }}>#{r.id}</span>
                <Link
                  href={`/dashboard/admin/orders?order=${r.order_draft_id}`}
                  onClick={(e) => e.stopPropagation()}
                  style={{ fontFamily: "monospace", color: "#2563eb", textDecoration: "none", fontWeight: 600 }}
                >
                  #{r.order_draft_id}
                </Link>
                <span style={{ color: "#0f172a", fontWeight: 500 }}>{r.carrier_code}</span>
                <span style={{ color: "#475569", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={r.reason}>
                  {r.reason}
                </span>
                <StatusBadge status={r.status} />
                <span style={{ fontSize: 12, color: "#94a3b8" }}>{formatDate(r.created_at)}</span>
              </div>
            ))
          )}

          {pages > 1 && (
            <div style={{ display: "flex", justifyContent: "center", gap: 6, padding: 16, borderTop: "1px solid #f1f5f9" }}>
              {Array.from({ length: pages }, (_, i) => i + 1).map((p) => (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  style={{ width: 32, height: 32, borderRadius: 8, border: "1px solid #e5e7eb", background: p === page ? "#0f172a" : "#fff", color: p === page ? "#fff" : "#0f172a", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
                >
                  {p}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Detail panel */}
        <div style={{ position: "sticky", top: 16 }}>
          {!selected ? (
            <div style={{ background: "#fff", border: "1px dashed #e5e7eb", borderRadius: 14, padding: 40, textAlign: "center", color: "#94a3b8", fontSize: 13 }}>
              Выберите заявку слева, чтобы увидеть детали и действия.
            </div>
          ) : (
            <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                <div style={{ fontSize: 15, fontWeight: 700, color: "#0f172a" }}>Заявка #{selected.id}</div>
                <StatusBadge status={selected.status} />
              </div>
              <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 4 }}>Заказ</div>
              <Link href={`/dashboard/admin/orders?order=${selected.order_draft_id}`} style={{ fontSize: 14, fontWeight: 600, color: "#2563eb", textDecoration: "none" }}>
                #{selected.order_draft_id}
              </Link>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 16 }}>
                <Field label="Перевозчик" value={selected.carrier_code} />
                <Field label="Создана" value={formatDate(selected.created_at)} />
              </div>

              <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 16, marginBottom: 4 }}>Причина</div>
              <div style={{ fontSize: 13, color: "#0f172a", padding: "10px 14px", background: "#f8fafc", borderRadius: 8, whiteSpace: "pre-wrap" }}>
                {selected.reason}
              </div>

              {selected.api_attempted && (
                <div style={{ marginTop: 12, padding: "10px 12px", background: "#fef3c7", borderRadius: 8, fontSize: 12, color: "#92400e" }}>
                  <b>API-отмена уже пробовалась.</b>
                  {selected.api_error && <div style={{ marginTop: 4, fontFamily: "monospace", fontSize: 11, wordBreak: "break-all" }}>{selected.api_error}</div>}
                </div>
              )}

              {selected.carrier_response && (
                <>
                  <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 12, marginBottom: 4 }}>Комментарий разрешившего</div>
                  <div style={{ fontSize: 13, color: "#0f172a", padding: "10px 14px", background: "#f8fafc", borderRadius: 8 }}>
                    {selected.carrier_response}
                  </div>
                </>
              )}

              {selected.status === "pending" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 18 }}>
                  <button
                    onClick={() => void handleApprove(selected.id)}
                    disabled={busyId === selected.id}
                    style={{ padding: "10px 16px", borderRadius: 10, border: "none", background: "#16a34a", color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", opacity: busyId === selected.id ? 0.6 : 1 }}
                  >
                    Подтвердить отмену (вручную)
                  </button>
                  {API_CARRIERS.has(selected.carrier_code) && (
                    <button
                      onClick={() => void handleRetry(selected.id)}
                      disabled={busyId === selected.id}
                      style={{ padding: "10px 16px", borderRadius: 10, border: "1px solid #c7d2fe", background: "#eef2ff", color: "#4338ca", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", opacity: busyId === selected.id ? 0.6 : 1 }}
                    >
                      Повторить API-отмену
                    </button>
                  )}
                  <button
                    onClick={() => void handleReject(selected.id)}
                    disabled={busyId === selected.id}
                    style={{ padding: "10px 16px", borderRadius: 10, border: "1px solid #fecaca", background: "#fff", color: "#dc2626", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", opacity: busyId === selected.id ? 0.6 : 1 }}
                  >
                    Отклонить
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 13, color: "#0f172a", fontWeight: 500 }}>{value}</div>
    </div>
  );
}
