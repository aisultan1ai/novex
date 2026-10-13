"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { cityLabel } from "@/lib/cities";
import {
  acceptCarrierOrder,
  getCarrierOrder,
  rejectCarrierOrder,
  uploadCarrierPod,
  type CarrierOrderItem,
} from "@/lib/api/carrier";
import {
  carrierApproveCancellation,
  carrierRejectCancellation,
} from "@/lib/api/cancellations";
import { orderStatusColors, useOrderStatusLabel } from "@/lib/status-labels";
import { TrackingTimeline } from "@/components/orders/tracking-timeline";
import { errorMessage } from "@/lib/api/client";
import { Link } from "@/i18n/navigation";

const ACCEPT_STATUSES = new Set(["sent_to_carrier", "pending_manual", "pending_manual_dispatch", "dispatch_failed"]);
const REJECT_STATUSES = new Set(["sent_to_carrier", "pending_manual", "pending_manual_dispatch"]);
const POD_STATUSES = new Set(["picked_up", "in_transit", "arrived", "delivered"]);

export default function CarrierOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const t = useTranslations("carrier.order");
  const locale = useLocale();
  const orderStatusLabel = useOrderStatusLabel();
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

  const [cancelBusy, setCancelBusy] = useState<"approve" | "reject" | null>(null);
  const [cancelRejectOpen, setCancelRejectOpen] = useState(false);
  const [cancelRejectReason, setCancelRejectReason] = useState("");
  const [cancelMsg, setCancelMsg] = useState<string | null>(null);

  const [trackingOpen, setTrackingOpen] = useState(false);

  const reload = async () => {
    try {
      const data = await getCarrierOrder(orderId);
      setOrder(data);
    } catch (e) {
      setError(errorMessage(e, t("errors.load")));
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
      setActionErr(errorMessage(e, t("errors.generic")));
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) { setActionErr(t("errors.rejectReason")); return; }
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
      setActionErr(errorMessage(e, t("errors.generic")));
    } finally {
      setActionLoading(false);
    }
  };

  const handleApproveCancellation = async (requestId: number) => {
    if (!window.confirm(t("cancelConfirm"))) return;
    setCancelBusy("approve");
    setCancelMsg(null);
    try {
      await carrierApproveCancellation(requestId);
      await reload();
    } catch (e) {
      setCancelMsg(errorMessage(e, t("errors.generic")));
    } finally {
      setCancelBusy(null);
    }
  };

  const handleRejectCancellation = async (requestId: number) => {
    const trimmed = cancelRejectReason.trim();
    if (trimmed.length < 3) {
      setCancelMsg(t("errors.reasonShort"));
      return;
    }
    setCancelBusy("reject");
    setCancelMsg(null);
    try {
      await carrierRejectCancellation(requestId, trimmed);
      setCancelRejectOpen(false);
      setCancelRejectReason("");
      await reload();
    } catch (e) {
      setCancelMsg(errorMessage(e, t("errors.generic")));
    } finally {
      setCancelBusy(null);
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
      setActionErr(errorMessage(e, t("errors.upload")));
    } finally {
      setPodLoading(false);
    }
  };

  if (loading) return <p style={{ color: "#5F6E7E" }}>{t("loading")}</p>;
  if (error || !order) return <div style={styles.errorBox}>{error ?? t("notFound")}</div>;

  const sender = order.parties.find((p) => p.role === "sender");
  const recipient = order.parties.find((p) => p.role === "recipient");
  const canAccept = ACCEPT_STATUSES.has(order.status);
  const canReject = REJECT_STATUSES.has(order.status);
  const canUploadPod = POD_STATUSES.has(order.status);

  return (
    <div style={{ maxWidth: 800 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <Link href="/dashboard/carrier/orders" style={{ color: "#4338ca", fontSize: 13, textDecoration: "none" }}>
          {t("back")}
        </Link>
        <span style={{ color: "#d1d5db" }}>|</span>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "#0E1826" }}>
          {t("title", { id: order.id })}
        </h2>
        <span style={{ ...styles.badge, ...(statusStyle(order.status)) }}>
          {orderStatusLabel(order.status)}
        </span>
      </div>

      {actionMsg && <div style={styles.successBox}>{actionMsg}</div>}
      {actionErr && <div style={styles.errorBox}>{actionErr}</div>}

      {/* Action buttons */}
      {(canAccept || canReject) && (
        <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap" }}>
          {canAccept && (
            <button onClick={handleAccept} disabled={actionLoading} style={styles.btnAccept}>
              {t("accept")}
            </button>
          )}
          {canReject && !showReject && (
            <button onClick={() => setShowReject(true)} disabled={actionLoading} style={styles.btnReject}>
              {t("reject")}
            </button>
          )}
          {canReject && showReject && (
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <input
                placeholder={t("rejectPlaceholder")}
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                style={styles.input}
              />
              <button onClick={handleReject} disabled={actionLoading} style={styles.btnReject}>{t("confirm")}</button>
              <button onClick={() => { setShowReject(false); setRejectReason(""); }} style={styles.btnCancel}>{t("cancel")}</button>
            </div>
          )}
        </div>
      )}

      {/* Carrier IDs - orderno / barcode returned by carrier API */}
      {(order.carrier_tracking_number || order.carrier_barcode) && (
        <div style={styles.card}>
          <div style={styles.cardTitle}>{t("ids")}</div>
          <div style={styles.row}>
            {order.carrier_tracking_number && (
              <div style={styles.col}>
                <div style={styles.label}>{t("orderNumber")}</div>
                <div style={{ ...styles.value, fontFamily: "monospace" }}>{order.carrier_tracking_number}</div>
              </div>
            )}
            {order.carrier_barcode && (
              <div style={styles.col}>
                <div style={styles.label}>{t("barcode")}</div>
                <div style={{ ...styles.value, fontFamily: "monospace" }}>{order.carrier_barcode}</div>
              </div>
            )}
            {order.tracking_number && (
              <div style={styles.col}>
                <div style={styles.label}>{t("novexId")}</div>
                <div style={{ ...styles.value, fontFamily: "monospace" }}>{order.tracking_number}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Route + info */}
      <div style={styles.card}>
        <div style={styles.cardTitle}>{t("routeAndTariff")}</div>
        <div style={styles.row}>
          <div style={styles.col}>
            <div style={styles.label}>{t("from")}</div>
            <div style={styles.value}>{cityLabel(order.from_city, locale)}</div>
          </div>
          <div style={styles.col}>
            <div style={styles.label}>{t("to")}</div>
            <div style={styles.value}>{cityLabel(order.to_city, locale)}</div>
          </div>
          <div style={styles.col}>
            <div style={styles.label}>{t("tariff")}</div>
            <div style={styles.value}>{order.tariff_name}</div>
          </div>
          <div style={styles.col}>
            <div style={styles.label}>{t("amount")}</div>
            <div style={styles.value}>{order.price.toLocaleString()} {order.currency}</div>
          </div>
          <div style={styles.col}>
            <div style={styles.label}>ETA</div>
            <div style={styles.value}>{t("days", { min: order.eta_days_min, max: order.eta_days_max })}</div>
          </div>
        </div>
      </div>

      {/* Parties */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
        {[sender, recipient].map((party, i) => party && (
          <div key={i} style={styles.card}>
            <div style={styles.cardTitle}>{i === 0 ? t("sender") : t("recipient")}</div>
            <div style={styles.label}>{t("name")}</div>
            <div style={styles.value}>{party.full_name}</div>
            <div style={styles.label}>{t("phone")}</div>
            <div style={styles.value}>{party.phone}</div>
            <div style={styles.label}>{t("address")}</div>
            <div style={styles.value}>{party.city}, {party.address_line1}{party.address_line2 ? `, ${party.address_line2}` : ""}</div>
            {party.postal_code && <><div style={styles.label}>{t("postalCode")}</div><div style={styles.value}>{party.postal_code}</div></>}
            {party.comment && <><div style={styles.label}>{t("comment")}</div><div style={styles.value}>{party.comment}</div></>}
          </div>
        ))}
      </div>

      {/* Packages */}
      <div style={styles.card}>
        <div style={styles.cardTitle}>{t("packages", { n: order.packages.length })}</div>
        {order.packages.map((pkg, i) => (
          <div key={i} style={{ paddingBottom: 8, marginBottom: 8, borderBottom: i < order.packages.length - 1 ? "1px solid #f3f4f6" : "none" }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>#{i + 1} - {pkg.description}</div>
            <div style={{ fontSize: 12, color: "#5F6E7E", display: "flex", gap: 16, flexWrap: "wrap" }}>
              <span>{t("pkgQty", { n: pkg.quantity })}</span>
              <span>{t("pkgWeight", { n: pkg.weight_kg })}</span>
              <span>{t("pkgSize", { w: pkg.width_cm, h: pkg.height_cm, d: pkg.depth_cm })}</span>
              {pkg.declared_value && <span>{t("pkgValue", { value: `${pkg.declared_value.toLocaleString()} ${pkg.declared_value_currency}` })}</span>}
            </div>
          </div>
        ))}
      </div>

      {/* POD upload */}
      {canUploadPod && (
        <div style={styles.card}>
          <div style={styles.cardTitle}>{t("pod.title")}</div>
          <p style={{ fontSize: 13, color: "#5F6E7E", marginBottom: 12 }}>
            {t("pod.hint")}
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
                {podLoading ? t("loading") : t("pod.upload")}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Uploaded PODs */}
      {(order.proof_of_delivery?.length ?? 0) > 0 && (
        <div style={styles.card}>
          <div style={styles.cardTitle}>{t("pod.uploaded", { n: order.proof_of_delivery!.length })}</div>
          {order.proof_of_delivery!.map((pod) => (
            <div key={pod.id} style={{ display: "flex", gap: 12, alignItems: "center", padding: "6px 0", borderBottom: "1px solid #f3f4f6" }}>
              <span style={{ fontSize: 13, flex: 1 }}>{pod.file_name}</span>
              <span style={{ fontSize: 11, color: "#9ca3af" }}>{new Date(pod.created_at).toLocaleDateString("ru-KZ")}</span>
              <a href={pod.file_url} target="_blank" rel="noreferrer" style={{ color: "#4338ca", fontSize: 12, fontWeight: 600 }}>
                {t("pod.download")}
              </a>
            </div>
          ))}
        </div>
      )}

      {/* Pending cancellation request — inline actions прямо в карточке заказа. */}
      {order.cancellation_request && order.cancellation_request.status === "pending" && (
        <div style={{ ...styles.card, borderColor: "#fde68a", background: "#fffbeb" }}>
          <div style={{ ...styles.cardTitle, color: "#92400e", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span>{t("cancelRequested")}</span>
            <span style={{ fontSize: 11, color: "#b45309", fontWeight: 500 }}>
              {new Date(order.cancellation_request.created_at).toLocaleString("ru-KZ")}
            </span>
          </div>
          <div style={{ fontSize: 13, color: "#78350f", marginBottom: 12 }}>
            <b>{t("reason")}</b> {order.cancellation_request.reason}
          </div>
          {cancelMsg && (
            <div style={{ marginBottom: 10, padding: "7px 12px", background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, fontSize: 12, color: "#991b1b" }}>
              {cancelMsg}
            </div>
          )}
          {!cancelRejectOpen ? (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button
                onClick={() => handleApproveCancellation(order.cancellation_request!.id)}
                disabled={cancelBusy !== null}
                style={{ padding: "8px 18px", borderRadius: 8, border: "none", background: "#16a34a", color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", opacity: cancelBusy ? 0.6 : 1 }}
              >
                {cancelBusy === "approve" ? t("approving") : t("approveCancel")}
              </button>
              <button
                onClick={() => setCancelRejectOpen(true)}
                disabled={cancelBusy !== null}
                style={{ padding: "8px 18px", borderRadius: 8, border: "1px solid #fecaca", background: "#fff", color: "#dc2626", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit", opacity: cancelBusy ? 0.6 : 1 }}
              >
                {t("reject")}
              </button>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <textarea
                value={cancelRejectReason}
                onChange={(e) => setCancelRejectReason(e.target.value)}
                placeholder={t("rejectCancelPlaceholder")}
                rows={2}
                style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #E2E8EE", fontSize: 13, fontFamily: "inherit", outline: "none", resize: "vertical" }}
              />
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={() => handleRejectCancellation(order.cancellation_request!.id)}
                  disabled={cancelBusy !== null}
                  style={{ padding: "8px 18px", borderRadius: 8, border: "none", background: "#dc2626", color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", opacity: cancelBusy ? 0.6 : 1 }}
                >
                  {cancelBusy === "reject" ? t("sending") : t("sendRejection")}
                </button>
                <button
                  onClick={() => { setCancelRejectOpen(false); setCancelRejectReason(""); setCancelMsg(null); }}
                  disabled={cancelBusy !== null}
                  style={{ padding: "8px 18px", borderRadius: 8, border: "1px solid #E2E8EE", background: "#fff", color: "#64748b", fontSize: 13, fontWeight: 500, cursor: "pointer", fontFamily: "inherit" }}
                >
                  {t("cancel")}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Customer review */}
      {order.review && (
        <div style={styles.card}>
          <div style={styles.cardTitle}>{t("review")}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: order.review.comment ? 8 : 0 }}>
            {[1, 2, 3, 4, 5].map((s) => (
              <span key={s} style={{ fontSize: 22, color: s <= order.review!.rating ? "#f59e0b" : "#E2E8EE", lineHeight: 1 }}>★</span>
            ))}
            <span style={{ fontSize: 13, color: "#64748b", marginLeft: 6 }}>
              {order.review.rating} / 5
            </span>
          </div>
          {order.review.comment && (
            <p style={{ margin: "6px 0 0", fontSize: 13, color: "#374151", lineHeight: 1.5, borderTop: "1px solid #f3f4f6", paddingTop: 8 }}>
              {order.review.comment}
            </p>
          )}
          <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 8 }}>
            {new Date(order.review.created_at).toLocaleString("ru-KZ")}
          </div>
        </div>
      )}

      {/* Tracking events — аккордеон, по умолчанию закрыт. */}
      {(order.tracking_events?.length ?? 0) > 0 && (
        <div style={{ ...styles.card, padding: trackingOpen ? "20px 24px" : "12px 16px" }}>
          <button
            type="button"
            onClick={() => setTrackingOpen((v) => !v)}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 8,
              padding: 0,
              background: "transparent",
              border: "none",
              cursor: "pointer",
              fontFamily: "inherit",
              textAlign: "left",
            }}
          >
            <span style={{ ...styles.cardTitle, marginBottom: 0 }}>
              {t("history", { n: order.tracking_events!.length })}
            </span>
            <span style={{ fontSize: 14, color: "#94a3b8", transform: trackingOpen ? "rotate(180deg)" : "rotate(0)", transition: "transform 0.15s" }}>
              ▾
            </span>
          </button>
          {trackingOpen && (
            <div style={{ marginTop: 16 }}>
              <TrackingTimeline events={order.tracking_events!} carrierCode={order.carrier_code} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function statusStyle(status: string): React.CSSProperties {
  const c = orderStatusColors(status);
  return { background: c.bg, color: c.color };
}

const styles: Record<string, React.CSSProperties> = {
  badge: { padding: "2px 10px", borderRadius: 12, fontSize: 12, fontWeight: 600, display: "inline-block" },
  card: { background: "#fff", border: "1px solid #E2E8EE", borderRadius: 10, padding: 16, marginBottom: 12 },
  cardTitle: { fontSize: 14, fontWeight: 700, color: "#0E1826", marginBottom: 10 },
  row: { display: "flex", gap: 20, flexWrap: "wrap" },
  col: { minWidth: 100 },
  label: { fontSize: 11, color: "#9ca3af", marginBottom: 2, marginTop: 6 },
  value: { fontSize: 14, color: "#0E1826" },
  successBox: { background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: "8px 14px", fontSize: 13, color: "#166534", marginBottom: 12 },
  errorBox: { background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "8px 14px", fontSize: 13, color: "#991b1b", marginBottom: 12 },
  btnAccept: { background: "#166534", color: "#fff", border: "none", borderRadius: 6, padding: "8px 18px", fontSize: 13, cursor: "pointer", fontWeight: 600 },
  btnReject: { background: "#991b1b", color: "#fff", border: "none", borderRadius: 6, padding: "8px 18px", fontSize: 13, cursor: "pointer", fontWeight: 600 },
  btnCancel: { background: "#f1f5f9", color: "#475569", border: "1px solid #E2E8EE", borderRadius: 6, padding: "8px 14px", fontSize: 13, cursor: "pointer" },
  input: { border: "1px solid #E2E8EE", borderRadius: 6, padding: "6px 10px", fontSize: 13, outline: "none", minWidth: 220 },
};
