"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  acceptCarrierOrder,
  getCarrierOrder,
  rejectCarrierOrder,
  uploadCarrierPod,
  type CarrierOrderItem,
} from "@/lib/api/carrier";

const STATUS_LABELS: Record<string, string> = {
  sent_to_carrier: "Передан перевозчику",
  pending_manual: "Ожидает обработки",
  pending_manual_dispatch: "Ожидает отправки",
  dispatch_failed: "Ошибка отправки",
  picked_up: "Принят",
  in_transit: "В пути",
  arrived: "Прибыл",
  delivered: "Доставлен",
};

const ACCEPT_STATUSES = new Set(["sent_to_carrier", "pending_manual", "pending_manual_dispatch", "dispatch_failed"]);
const REJECT_STATUSES = new Set(["sent_to_carrier", "pending_manual", "pending_manual_dispatch"]);
const POD_STATUSES = new Set(["picked_up", "in_transit", "arrived", "delivered"]);

export default function CarrierOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const orderId = Number(id);

  const [order, setOrder] = useState<CarrierOrderItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showReject, setShowReject] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);

  const [podFile, setPodFile] = useState<File | null>(null);
  const [podLoading, setPodLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const reload = async () => {
    try {
      const data = await getCarrierOrder(orderId);
      setOrder(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
    }
  };

  useEffect(() => {
    (async () => {
      setLoading(true);
      await reload();
      setLoading(false);
    })();
  }, [orderId]);

  const handleAccept = async () => {
    setActionLoading(true);
    setActionMsg(null);
    setActionErr(null);
    try {
      const res = await acceptCarrierOrder(orderId);
      setActionMsg(res.message);
      await reload();
    } catch (e) {
      setActionErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) { setActionErr("Укажите причину отклонения"); return; }
    setActionLoading(true);
    setActionMsg(null);
    setActionErr(null);
    try {
      const res = await rejectCarrierOrder(orderId, rejectReason);
      setActionMsg(res.message);
      setShowReject(false);
      setRejectReason("");
      await reload();
    } catch (e) {
      setActionErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setActionLoading(false);
    }
  };

  const handleUploadPod = async () => {
    if (!podFile) return;
    setPodLoading(true);
    setActionMsg(null);
    setActionErr(null);
    try {
      const res = await uploadCarrierPod(orderId, podFile);
      setActionMsg(res.message);
      setPodFile(null);
      if (fileRef.current) fileRef.current.value = "";
      await reload();
    } catch (e) {
      setActionErr(e instanceof Error ? e.message : "Ошибка загрузки файла");
    } finally {
      setPodLoading(false);
    }
  };

  if (loading) return <p style={{ color: "#6b7280" }}>Загрузка...</p>;
  if (error || !order) return <div style={styles.errorBox}>{error ?? "Заказ не найден"}</div>;

  const sender = order.parties.find((p) => p.role === "sender");
  const recipient = order.parties.find((p) => p.role === "recipient");
  const canAccept = ACCEPT_STATUSES.has(order.status);
  const canReject = REJECT_STATUSES.has(order.status);
  const canUploadPod = POD_STATUSES.has(order.status);

  return (
    <div style={{ maxWidth: 800 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <Link href="/dashboard/carrier/orders" style={{ color: "#4338ca", fontSize: 13, textDecoration: "none" }}>
          ← Все заказы
        </Link>
        <span style={{ color: "#d1d5db" }}>|</span>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "#111827" }}>
          Заказ #{order.id}
        </h2>
        <span style={{ ...styles.badge, ...(statusStyle(order.status)) }}>
          {STATUS_LABELS[order.status] ?? order.status}
        </span>
      </div>

      {actionMsg && <div style={styles.successBox}>{actionMsg}</div>}
      {actionErr && <div style={styles.errorBox}>{actionErr}</div>}

      {/* Action buttons */}
      {(canAccept || canReject) && (
        <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap" }}>
          {canAccept && (
            <button onClick={handleAccept} disabled={actionLoading} style={styles.btnAccept}>
              Принять заказ
            </button>
          )}
          {canReject && !showReject && (
            <button onClick={() => setShowReject(true)} disabled={actionLoading} style={styles.btnReject}>
              Отклонить
            </button>
          )}
          {canReject && showReject && (
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <input
                placeholder="Причина отклонения..."
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                style={styles.input}
              />
              <button onClick={handleReject} disabled={actionLoading} style={styles.btnReject}>Подтвердить</button>
              <button onClick={() => { setShowReject(false); setRejectReason(""); }} style={styles.btnCancel}>Отмена</button>
            </div>
          )}
        </div>
      )}

      {/* Route + info */}
      <div style={styles.card}>
        <div style={styles.cardTitle}>Маршрут и тариф</div>
        <div style={styles.row}>
          <div style={styles.col}>
            <div style={styles.label}>Откуда</div>
            <div style={styles.value}>{order.from_city}</div>
          </div>
          <div style={styles.col}>
            <div style={styles.label}>Куда</div>
            <div style={styles.value}>{order.to_city}</div>
          </div>
          <div style={styles.col}>
            <div style={styles.label}>Тариф</div>
            <div style={styles.value}>{order.tariff_name}</div>
          </div>
          <div style={styles.col}>
            <div style={styles.label}>Сумма</div>
            <div style={styles.value}>{order.price.toLocaleString()} {order.currency}</div>
          </div>
          <div style={styles.col}>
            <div style={styles.label}>ETA</div>
            <div style={styles.value}>{order.eta_days_min}-{order.eta_days_max} дн.</div>
          </div>
        </div>
      </div>

      {/* Parties */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
        {[sender, recipient].map((party, i) => party && (
          <div key={i} style={styles.card}>
            <div style={styles.cardTitle}>{i === 0 ? "Отправитель" : "Получатель"}</div>
            <div style={styles.label}>Имя</div>
            <div style={styles.value}>{party.full_name}</div>
            <div style={styles.label}>Телефон</div>
            <div style={styles.value}>{party.phone}</div>
            <div style={styles.label}>Адрес</div>
            <div style={styles.value}>{party.city}, {party.address_line1}{party.address_line2 ? `, ${party.address_line2}` : ""}</div>
            {party.postal_code && <><div style={styles.label}>Индекс</div><div style={styles.value}>{party.postal_code}</div></>}
            {party.comment && <><div style={styles.label}>Комментарий</div><div style={styles.value}>{party.comment}</div></>}
          </div>
        ))}
      </div>

      {/* Packages */}
      <div style={styles.card}>
        <div style={styles.cardTitle}>Посылки ({order.packages.length})</div>
        {order.packages.map((pkg, i) => (
          <div key={i} style={{ paddingBottom: 8, marginBottom: 8, borderBottom: i < order.packages.length - 1 ? "1px solid #f3f4f6" : "none" }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>#{i + 1} - {pkg.description}</div>
            <div style={{ fontSize: 12, color: "#6b7280", display: "flex", gap: 16, flexWrap: "wrap" }}>
              <span>Кол-во: {pkg.quantity}</span>
              <span>Вес: {pkg.weight_kg} кг</span>
              <span>Размер: {pkg.width_cm}×{pkg.height_cm}×{pkg.depth_cm} см</span>
              {pkg.declared_value && <span>Стоимость: {pkg.declared_value.toLocaleString()} {pkg.declared_value_currency}</span>}
            </div>
          </div>
        ))}
      </div>

      {/* POD upload */}
      {canUploadPod && (
        <div style={styles.card}>
          <div style={styles.cardTitle}>Подтверждение доставки (POD)</div>
          <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 12 }}>
            Загрузите фото или PDF с подписью получателя. После загрузки заказ перейдёт в статус «Доставлен».
          </p>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <input
              type="file"
              ref={fileRef}
              accept=".jpg,.jpeg,.png,.pdf"
              onChange={(e) => setPodFile(e.target.files?.[0] ?? null)}
              style={{ fontSize: 13 }}
            />
            {podFile && (
              <button onClick={handleUploadPod} disabled={podLoading} style={styles.btnAccept}>
                {podLoading ? "Загрузка..." : "Загрузить"}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Uploaded PODs */}
      {(order.proof_of_delivery?.length ?? 0) > 0 && (
        <div style={styles.card}>
          <div style={styles.cardTitle}>Загруженные POD ({order.proof_of_delivery!.length})</div>
          {order.proof_of_delivery!.map((pod) => (
            <div key={pod.id} style={{ display: "flex", gap: 12, alignItems: "center", padding: "6px 0", borderBottom: "1px solid #f3f4f6" }}>
              <span style={{ fontSize: 13, flex: 1 }}>{pod.file_name}</span>
              <span style={{ fontSize: 11, color: "#9ca3af" }}>{new Date(pod.created_at).toLocaleDateString("ru-KZ")}</span>
              <a href={pod.file_url} target="_blank" rel="noreferrer" style={{ color: "#4338ca", fontSize: 12, fontWeight: 600 }}>
                Скачать
              </a>
            </div>
          ))}
        </div>
      )}

      {/* Tracking events */}
      {(order.tracking_events?.length ?? 0) > 0 && (
        <div style={styles.card}>
          <div style={styles.cardTitle}>История статусов</div>
          {order.tracking_events!.map((e, i) => (
            <div key={i} style={{ padding: "6px 0", borderBottom: "1px solid #f3f4f6", fontSize: 13 }}>
              <span style={{ fontWeight: 600 }}>{STATUS_LABELS[e.status] ?? e.status}</span>
              {e.location && <span style={{ color: "#6b7280", marginLeft: 8 }}>📍 {e.location}</span>}
              {e.description && <div style={{ color: "#6b7280", fontSize: 12 }}>{e.description}</div>}
              <div style={{ fontSize: 11, color: "#9ca3af" }}>{new Date(e.occurred_at).toLocaleString("ru-KZ")}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function statusStyle(status: string): React.CSSProperties {
  const map: Record<string, React.CSSProperties> = {
    sent_to_carrier: { background: "#dbeafe", color: "#1e40af" },
    pending_manual: { background: "#fef9c3", color: "#854d0e" },
    dispatch_failed: { background: "#fee2e2", color: "#991b1b" },
    picked_up: { background: "#dcfce7", color: "#166534" },
    in_transit: { background: "#dbeafe", color: "#1e40af" },
    arrived: { background: "#ede9fe", color: "#5b21b6" },
    delivered: { background: "#dcfce7", color: "#166534" },
  };
  return map[status] ?? { background: "#f1f5f9", color: "#475569" };
}

const styles: Record<string, React.CSSProperties> = {
  badge: { padding: "2px 10px", borderRadius: 12, fontSize: 12, fontWeight: 600, display: "inline-block" },
  card: { background: "#fff", border: "1px solid #e5e7eb", borderRadius: 10, padding: 16, marginBottom: 12 },
  cardTitle: { fontSize: 14, fontWeight: 700, color: "#111827", marginBottom: 10 },
  row: { display: "flex", gap: 20, flexWrap: "wrap" },
  col: { minWidth: 100 },
  label: { fontSize: 11, color: "#9ca3af", marginBottom: 2, marginTop: 6 },
  value: { fontSize: 14, color: "#111827" },
  successBox: { background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: "8px 14px", fontSize: 13, color: "#166534", marginBottom: 12 },
  errorBox: { background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "8px 14px", fontSize: 13, color: "#991b1b", marginBottom: 12 },
  btnAccept: { background: "#166534", color: "#fff", border: "none", borderRadius: 6, padding: "8px 18px", fontSize: 13, cursor: "pointer", fontWeight: 600 },
  btnReject: { background: "#991b1b", color: "#fff", border: "none", borderRadius: 6, padding: "8px 18px", fontSize: 13, cursor: "pointer", fontWeight: 600 },
  btnCancel: { background: "#f1f5f9", color: "#475569", border: "1px solid #e5e7eb", borderRadius: 6, padding: "8px 14px", fontSize: 13, cursor: "pointer" },
  input: { border: "1px solid #e5e7eb", borderRadius: 6, padding: "6px 10px", fontSize: 13, outline: "none", minWidth: 220 },
};
