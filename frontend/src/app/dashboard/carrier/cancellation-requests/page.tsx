"use client";

import { useCallback, useEffect, useState } from "react";

import {
  carrierApproveCancellation,
  carrierListCancellations,
  carrierRejectCancellation,
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

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("ru-KZ", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function StatusBadge({ status }: { status: CancellationStatus }) {
  const { bg, color } = STATUS_COLORS[status];
  return (
    <span style={{ display: "inline-block", padding: "3px 10px", borderRadius: 999, background: bg, color, fontSize: 12, fontWeight: 700 }}>
      {STATUS_LABELS[status]}
    </span>
  );
}

export default function CarrierCancellationRequestsPage() {
  const [items, setItems] = useState<CancellationRequestFull[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<CancellationStatus | "all">("pending");
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await carrierListCancellations({
        status: statusFilter === "all" ? undefined : statusFilter,
        page: 1,
        size: 50,
      });
      setItems(resp.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить заявки");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { void load(); }, [load]);

  async function handleApprove(id: number) {
    if (!window.confirm("Подтверждаете отмену? Заказ будет закрыт у Novex, клиент получит уведомление.")) return;
    setBusyId(id);
    try {
      await carrierApproveCancellation(id);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setBusyId(null);
    }
  }

  async function handleReject(id: number) {
    const comment = window.prompt("Причина отказа (обязательно, минимум 3 символа) - клиент увидит этот текст:");
    if (!comment || comment.trim().length < 3) return;
    setBusyId(id);
    try {
      await carrierRejectCancellation(id, comment.trim());
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
          {(["pending", "approved", "rejected", "all"] as const).map((s) => (
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
              {s === "all" ? "Все" : STATUS_LABELS[s as CancellationStatus]}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div style={{ padding: "12px 16px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 13 }}>
          {error}
        </div>
      )}

      {loading ? (
        <div style={{ padding: 40, textAlign: "center", color: "#64748b", fontSize: 14 }}>Загружаем…</div>
      ) : items.length === 0 ? (
        <div style={{ padding: "60px 20px", textAlign: "center", color: "#64748b", fontSize: 14, background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14 }}>
          Заявок с такими фильтрами нет
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {items.map((r) => (
            <div key={r.id} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 8 }}>
                <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                  <span style={{ fontSize: 15, fontWeight: 700, color: "#0f172a" }}>Заявка #{r.id}</span>
                  <span style={{ fontSize: 13, color: "#64748b" }}>
                    Заказ <span style={{ fontFamily: "monospace", color: "#334155", fontWeight: 600 }}>#{r.order_draft_id}</span>
                  </span>
                  <StatusBadge status={r.status} />
                </div>
                <span style={{ fontSize: 12, color: "#94a3b8" }}>{formatDate(r.created_at)}</span>
              </div>

              <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 4 }}>Причина клиента</div>
              <div style={{ fontSize: 13, color: "#0f172a", padding: "10px 14px", background: "#f8fafc", borderRadius: 8, whiteSpace: "pre-wrap", marginBottom: 12 }}>
                {r.reason}
              </div>

              {r.carrier_response && (
                <>
                  <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 4 }}>Ваш ответ</div>
                  <div style={{ fontSize: 13, color: "#0f172a", padding: "10px 14px", background: "#f8fafc", borderRadius: 8, marginBottom: 12 }}>
                    {r.carrier_response}
                  </div>
                </>
              )}

              {r.status === "pending" && (
                <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                  <button
                    onClick={() => void handleApprove(r.id)}
                    disabled={busyId === r.id}
                    style={{ padding: "9px 20px", borderRadius: 10, border: "none", background: "#16a34a", color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", opacity: busyId === r.id ? 0.6 : 1 }}
                  >
                    Подтверждаю, отменил у себя
                  </button>
                  <button
                    onClick={() => void handleReject(r.id)}
                    disabled={busyId === r.id}
                    style={{ padding: "9px 20px", borderRadius: 10, border: "1px solid #fecaca", background: "#fff", color: "#dc2626", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", opacity: busyId === r.id ? 0.6 : 1 }}
                  >
                    Отклонить
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
