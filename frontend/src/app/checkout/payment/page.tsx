"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

interface BankDetails {
  recipient_name: string;
  bank_name: string;
  iban: string;
  bin: string;
  knp: string;
  purpose: string;
  amount: string;
  currency: string;
}

interface PaymentData {
  payment_id: number;
  order_reference: string;
  status: string;
  bank_details: BankDetails;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

async function initiatePayment(orderId: string): Promise<PaymentData> {
  const res = await fetch(
    `${API_BASE}/api/v1/payments/orders/${orderId}/initiate-bank-transfer`,
    {
      method: "POST",
      credentials: "include",
    }
  );
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail ?? "Ошибка инициализации платежа");
  }
  return res.json();
}

async function getPaymentStatus(orderId: string): Promise<{ status: string }> {
  const res = await fetch(
    `${API_BASE}/api/v1/payments/orders/${orderId}/payment-status`,
    { credentials: "include" }
  );
  if (!res.ok) return { status: "unknown" };
  return res.json();
}

const STATUS_LABELS: Record<string, string> = {
  awaiting_payment: "Ожидает оплаты",
  payment_under_review: "Оплата на проверке",
  paid: "Оплачено",
  payment_rejected: "Оплата отклонена",
  cancelled: "Отменён",
};

export default function PaymentPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const orderId = searchParams.get("orderId") ?? "";

  const [paymentData, setPaymentData] = useState<PaymentData | null>(null);
  const [status, setStatus] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
    pollingRef.current = setInterval(async () => {
      const s = await getPaymentStatus(orderId);
      setStatus(s.status);
      if (s.status === "paid" || s.status === "cancelled") {
        clearInterval(pollingRef.current!);
        if (s.status === "paid") router.push(`/dashboard/orders`);
      }
    }, 5000);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [uploadSuccess, orderId, router]);

  const handleUpload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!fileInputRef.current?.files?.[0] || !paymentData) return;
    const file = fileInputRef.current.files[0];

    setUploading(true);
    setUploadError(null);

    const form = new FormData();
    form.append("payment_id", String(paymentData.payment_id));
    form.append("file", file);

    const res = await fetch(
      `${API_BASE}/api/v1/payments/orders/${orderId}/upload-proof`,
      { method: "POST", credentials: "include", body: form }
    );

    setUploading(false);

    if (!res.ok) {
      const err = await res.json();
      setUploadError(err.detail ?? "Ошибка загрузки");
      return;
    }

    setUploadSuccess(true);
    setStatus("payment_under_review");
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
            Статус обновляется автоматически.
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
              <p style={styles.muted}>
                После оплаты загрузите скриншот или PDF квитанции.
                Форматы: JPEG, PNG, PDF. Макс. размер: 5 МБ.
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
                  {uploading ? "Загрузка..." : "Я оплатил — загрузить чек"}
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
