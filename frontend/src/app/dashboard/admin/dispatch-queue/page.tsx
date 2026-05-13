"use client";

import { useEffect, useState } from "react";
import { getDispatchQueue, markDispatched, retryDispatch } from "@/lib/api/carrier_webhooks";
import type { DispatchQueueItem } from "@/types/carrier_webhooks";

export default function DispatchQueuePage() {
  const [items, setItems] = useState<DispatchQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<Record<number, boolean>>({});
  const [modalId, setModalId] = useState<number | null>(null);
  const [trackingInput, setTrackingInput] = useState("");

  const load = () => {
    setLoading(true);
    getDispatchQueue()
      .then((r) => setItems(r.items))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, []);

  const handleRetry = async (id: number) => {
    setRetrying((p) => ({ ...p, [id]: true }));
    try {
      await retryDispatch(id);
      load();
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setRetrying((p) => ({ ...p, [id]: false }));
    }
  };

  const handleMarkDispatched = async () => {
    if (!modalId || !trackingInput.trim()) return;
    try {
      await markDispatched(modalId, trackingInput.trim());
      setModalId(null);
      setTrackingInput("");
      load();
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  const statusLabel = (s: string) =>
    s === "dispatch_failed" ? "Ошибка отправки" : "Ручная передача";

  const statusColor = (s: string): React.CSSProperties =>
    s === "dispatch_failed"
      ? { background: "#fee2e2", color: "#991b1b" }
      : { background: "#fef9c3", color: "#854d0e" };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>Очередь заказов</h2>
        <button onClick={load}
          style={{ padding: "7px 16px", background: "#f1f5f9", border: "1px solid #e2e8f0", borderRadius: 8, cursor: "pointer", fontSize: 13 }}>
          Обновить
        </button>
      </div>

      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "10px 16px", marginBottom: 16, color: "#991b1b" }}>
          {error}
          <button onClick={() => setError(null)} style={{ marginLeft: 12, background: "none", border: "none", cursor: "pointer", color: "#991b1b" }}>✕</button>
        </div>
      )}

      {modalId !== null && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50 }}>
          <div style={{ background: "#fff", borderRadius: 12, padding: 28, width: 400, boxShadow: "0 20px 60px rgba(0,0,0,0.2)" }}>
            <h3 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 700 }}>Ввести номер отслеживания</h3>
            <input
              value={trackingInput}
              onChange={(e) => setTrackingInput(e.target.value)}
              placeholder="Tracking number от перевозчика"
              style={{ width: "100%", padding: "9px 12px", border: "1px solid #cbd5e1", borderRadius: 8, fontSize: 14, boxSizing: "border-box" }}
            />
            <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
              <button onClick={handleMarkDispatched}
                style={{ flex: 1, padding: "9px", background: "#0f172a", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>
                Сохранить
              </button>
              <button onClick={() => { setModalId(null); setTrackingInput(""); }}
                style={{ flex: 1, padding: "9px", background: "#e2e8f0", color: "#334155", border: "none", borderRadius: 8, cursor: "pointer" }}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div style={{ color: "#64748b", fontSize: 14 }}>Загрузка...</div>
      ) : items.length === 0 ? (
        <div style={{ color: "#64748b", fontSize: 14, padding: 32, textAlign: "center" }}>Очередь пуста</div>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "#f1f5f9" }}>
              <th style={th}>ID</th>
              <th style={th}>Перевозчик</th>
              <th style={th}>Статус</th>
              <th style={th}>Ошибка</th>
              <th style={th}>Время</th>
              <th style={th}>Действия</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
                <td style={td}>#{item.id}</td>
                <td style={td}>
                  <div style={{ fontWeight: 600 }}>{item.carrier_name_snapshot}</div>
                  <div style={{ color: "#64748b", fontSize: 11 }}>{item.carrier_code_snapshot}</div>
                </td>
                <td style={td}>
                  <span style={{ padding: "3px 10px", borderRadius: 99, fontSize: 12, fontWeight: 600, ...statusColor(item.status) }}>
                    {statusLabel(item.status)}
                  </span>
                </td>
                <td style={{ ...td, maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#64748b" }}>
                  {item.dispatch_error ?? "-"}
                </td>
                <td style={{ ...td, color: "#64748b" }}>{new Date(item.created_at).toLocaleString("ru-RU")}</td>
                <td style={td}>
                  <button
                    onClick={() => handleRetry(item.id)}
                    disabled={retrying[item.id]}
                    style={{ padding: "4px 12px", background: "#e0f2fe", color: "#0369a1", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12, marginRight: 6, opacity: retrying[item.id] ? 0.6 : 1 }}>
                    {retrying[item.id] ? "..." : "Повторить"}
                  </button>
                  <button
                    onClick={() => { setModalId(item.id); setTrackingInput(""); }}
                    style={{ padding: "4px 12px", background: "#f1f5f9", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12 }}>
                    Ввести номер
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

const th: React.CSSProperties = { padding: "10px 12px", textAlign: "left", fontWeight: 600, color: "#475569", fontSize: 12 };
const td: React.CSSProperties = { padding: "10px 12px", color: "#1e293b" };
