"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  initiatePayment,
  getPaymentStatus,
  uploadPaymentProof,
  type PaymentData,
} from "@/lib/api/payments";

const STATUS_LABELS: Record<string, string> = {
  awaiting_payment: "Ожидает оплаты",
  payment_under_review: "Оплата на проверке",
  paid: "Оплачено",
  dispatch_queued: "Оплачено",
  payment_rejected: "Оплата отклонена",
  cancelled: "Отменён",
  poll_timeout: "Ожидание подтверждения",
};

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB
const POLL_INTERVAL_MS = 5000;
const POLL_MAX_ATTEMPTS = 360; // 30 minutes at 5 s intervals

export default function PaymentPage() {
  return (
    <Suspense fallback={<div style={styles.container}><p style={styles.muted}>Загрузка...</p></div>}>
      <PaymentPageContent />
    </Suspense>
  );
}

function PaymentPageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const orderId = searchParams.get("orderId") ?? "";

  const [paymentData, setPaymentData] = useState<PaymentData | null>(null);
  const [status, setStatus] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [pollTimedOut, setPollTimedOut] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollAttemptsRef = useRef(0);

  useEffect(() => {
    if (!orderId) {
      setError("Заказ не найден");
      setLoading(false);
      return;
    }
    initiatePayment(orderId)
      .then((data) => {
        setPaymentData(data);
        setStatus(data.status);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [orderId]);

  // Poll payment status after proof upload
  useEffect(() => {
    if (!uploadSuccess) return;
    pollAttemptsRef.current = 0;

    pollingRef.current = setInterval(async () => {
      pollAttemptsRef.current += 1;

      if (pollAttemptsRef.current >= POLL_MAX_ATTEMPTS) {
        clearInterval(pollingRef.current!);
        setPollTimedOut(true);
        return;
      }

      const s = await getPaymentStatus(orderId);
      setStatus(s.status);
      if (s.status === "paid" || s.status === "dispatch_queued") {
        clearInterval(pollingRef.current!);
        router.push(`/dashboard/orders`);
      } else if (s.status === "cancelled") {
        clearInterval(pollingRef.current!);
      } else if (s.status === "payment_rejected") {
        clearInterval(pollingRef.current!);
        setUploadSuccess(false);
        setUploadError("Ваш чек отклонён оператором. Загрузите корректный документ об оплате.");
      }
    }, POLL_INTERVAL_MS);

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [uploadSuccess, orderId, router]);

  const handleUpload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file || !paymentData) return;

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setUploadError("Файл слишком большой. Максимальный размер: 5 МБ.");
      return;
    }

    setUploading(true);
    setUploadError(null);

    try {
      await uploadPaymentProof(orderId, paymentData.payment_id, file);
      setUploadSuccess(true);
      setStatus("payment_under_review");
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Ошибка загрузки файла";
      setUploadError(detail);
    } finally {
      setUploading(false);
    }
  };

  if (loading) {
    return (
      <div style={styles.container}>
        <p style={styles.muted}>Загрузка...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.container}>
        <p style={{ color: "#dc2626" }}>{error}</p>
      </div>
    );
  }

  const d = paymentData!.bank_details;

  return (
    <div style={styles.container}>
      <button onClick={() => router.push("/dashboard/orders")} style={styles.backBtn}>
        ← Назад к заказам
      </button>
      <h1 style={styles.title}>Оплата заказа</h1>
      <p style={styles.ref}>Заказ: {paymentData!.order_reference}</p>

      {/* Status badge */}
      <div style={{ ...styles.badge, ...statusBadgeStyle(status) }}>
        {STATUS_LABELS[status] ?? status}
      </div>

      {uploadSuccess ? (
        <div style={styles.successBox}>
          <p style={styles.successText}>
            Чек загружен. Оплата отправлена на проверку оператором.
          </p>
          <p style={styles.muted}>
            Обычно подтверждение занимает до 24 часов в рабочие дни.
            {pollTimedOut
              ? " Автоматическая проверка завершена. Обновите страницу или обратитесь в поддержку, если оплата не подтверждается."
              : " Статус обновляется автоматически."}
          </p>
        </div>
      ) : (
        <>
          {/* Requisites */}
          <div style={styles.card}>
            <h2 style={styles.cardTitle}>Реквизиты для оплаты</h2>
            <ReqRow label="Получатель" value={d.recipient_name} />
            <ReqRow label="Банк" value={d.bank_name} />
            <ReqRow label="IBAN" value={d.iban} copy />
            <ReqRow label="БИН" value={d.bin} />
            <ReqRow label="КНП" value={d.knp} />
            <ReqRow label="Назначение платежа" value={d.purpose} copy />
            <div style={styles.amountRow}>
              <span style={styles.amountLabel}>Сумма</span>
              <span style={styles.amount}>
                {d.amount} {d.currency}
              </span>
            </div>
          </div>

          {/* Upload form */}
          {status !== "paid" && (
            <div style={styles.card}>
              <h2 style={styles.cardTitle}>Подтверждение оплаты</h2>
              <ol style={{ ...styles.muted, paddingLeft: 18, margin: "0 0 12px", lineHeight: 1.8 }}>
                <li>Переведите точную сумму по реквизитам выше.</li>
                <li>В назначении платежа укажите номер заказа (скопируйте поле «Назначение платежа»).</li>
                <li>Сохраните скриншот или PDF-квитанцию из вашего банка.</li>
                <li>Загрузите файл ниже - оператор проверит оплату в течение 24 ч.</li>
              </ol>
              <p style={{ ...styles.muted, fontSize: 12, color: "#94a3b8" }}>
                Принимаются: JPEG, PNG, PDF. Максимальный размер: 5 МБ.
              </p>
              <form onSubmit={handleUpload} style={styles.form}>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,application/pdf"
                  required
                  style={styles.fileInput}
                />
                {uploadError && (
                  <p style={{ color: "#dc2626", fontSize: 14 }}>{uploadError}</p>
                )}
                <button type="submit" disabled={uploading} style={styles.btn}>
                  {uploading ? "Загрузка..." : "Я оплатил - загрузить чек"}
                </button>
              </form>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ReqRow({
  label,
  value,
  copy,
}: {
  label: string;
  value: string;
  copy?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div style={styles.reqRow}>
      <span style={styles.reqLabel}>{label}</span>
      <span style={styles.reqValue}>
        {value}
        {copy && (
          <button onClick={handleCopy} style={styles.copyBtn}>
            {copied ? "✓" : "Копировать"}
          </button>
        )}
      </span>
    </div>
  );
}

function statusBadgeStyle(status: string): React.CSSProperties {
  const map: Record<string, React.CSSProperties> = {
    awaiting_payment: { background: "#fef9c3", color: "#854d0e" },
    payment_under_review: { background: "#dbeafe", color: "#1e40af" },
    paid: { background: "#dcfce7", color: "#166534" },
    payment_rejected: { background: "#fee2e2", color: "#991b1b" },
    cancelled: { background: "#f1f5f9", color: "#475569" },
  };
  return map[status] ?? { background: "#f1f5f9", color: "#475569" };
}

const styles: Record<string, React.CSSProperties> = {
  container: { maxWidth: 620, margin: "40px auto", padding: "0 16px" },
  backBtn: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    marginBottom: 20,
    padding: "6px 14px",
    borderRadius: 8,
    border: "1px solid #e5e7eb",
    background: "#f8fafc",
    fontSize: 13,
    fontWeight: 500,
    color: "#374151",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  title: { fontSize: 24, fontWeight: 700, marginBottom: 4 },
  ref: { color: "#6b7280", marginBottom: 16, fontSize: 14 },
  badge: {
    display: "inline-block",
    padding: "4px 12px",
    borderRadius: 20,
    fontSize: 13,
    fontWeight: 600,
    marginBottom: 20,
  },
  card: {
    border: "1px solid #e5e7eb",
    borderRadius: 12,
    padding: 20,
    marginBottom: 20,
    background: "#fff",
  },
  cardTitle: { fontSize: 16, fontWeight: 700, marginBottom: 14 },
  reqRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "8px 0",
    borderBottom: "1px solid #f3f4f6",
  },
  reqLabel: { color: "#6b7280", fontSize: 13, minWidth: 160 },
  reqValue: { fontWeight: 500, fontSize: 14, display: "flex", gap: 8, alignItems: "center" },
  copyBtn: {
    fontSize: 11,
    padding: "2px 8px",
    background: "#f1f5f9",
    border: "1px solid #e2e8f0",
    borderRadius: 4,
    cursor: "pointer",
    color: "#374151",
  },
  amountRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    paddingTop: 12,
    marginTop: 4,
  },
  amountLabel: { color: "#6b7280", fontSize: 13 },
  amount: { fontSize: 22, fontWeight: 800, color: "#111827" },
  form: { display: "flex", flexDirection: "column", gap: 12, marginTop: 12 },
  fileInput: { fontSize: 14 },
  btn: {
    background: "#1d4ed8",
    color: "#fff",
    padding: "10px 20px",
    border: "none",
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  },
  successBox: {
    background: "#f0fdf4",
    border: "1px solid #bbf7d0",
    borderRadius: 12,
    padding: 20,
  },
  successText: { color: "#166534", fontWeight: 600, marginBottom: 8 },
  muted: { color: "#6b7280", fontSize: 14 },
};
