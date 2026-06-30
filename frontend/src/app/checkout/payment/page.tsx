"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Copy, Check } from "lucide-react";
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

const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  awaiting_payment:     { bg: "#FEF3C7", color: "#92400E" },
  payment_under_review: { bg: "#DBEAFE", color: "#1E40AF" },
  paid:                 { bg: "#DCFCE7", color: "#166534" },
  dispatch_queued:      { bg: "#DCFCE7", color: "#166534" },
  payment_rejected:     { bg: "#FEE2E2", color: "#991B1B" },
  cancelled:            { bg: "#F1F5F9", color: "#475569" },
};

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024;
const POLL_INTERVAL_MS = 5000;
const POLL_MAX_ATTEMPTS = 360;

export default function PaymentPage() {
  return (
    <Suspense fallback={
      <div style={{ minHeight: "100vh", background: "#FAFAFA", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <p style={{ font: "400 14px/1 Inter Variable, sans-serif", color: "#6B7280" }}>Загрузка...</p>
      </div>
    }>
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
        router.push("/dashboard/orders");
      } else if (s.status === "cancelled") {
        clearInterval(pollingRef.current!);
      } else if (s.status === "payment_rejected") {
        clearInterval(pollingRef.current!);
        setUploadSuccess(false);
        setUploadError("Ваш чек отклонён оператором. Загрузите корректный документ об оплате.");
      }
    }, POLL_INTERVAL_MS);

    return () => { if (pollingRef.current) clearInterval(pollingRef.current); };
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
      setUploadError(err instanceof Error ? err.message : "Ошибка загрузки файла");
    } finally {
      setUploading(false);
    }
  };

  const card = {
    background: "#ffffff",
    border: "1px solid #E5E7EB",
    borderRadius: 16,
    boxShadow: "0 2px 8px rgba(17,24,39,0.04)",
    padding: "24px 28px",
    marginBottom: 16,
  };

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: "#FAFAFA", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <p style={{ font: "400 14px/1 Inter Variable, sans-serif", color: "#6B7280" }}>Загрузка...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ minHeight: "100vh", background: "#FAFAFA", display: "flex", alignItems: "center", justifyContent: "center", padding: "0 16px" }}>
        <div style={{ maxWidth: 480, width: "100%", background: "#ffffff", border: "1px solid #E5E7EB", borderRadius: 16, padding: "32px 28px", textAlign: "center" }}>
          <p style={{ font: "400 14px/1.5 Inter Variable, sans-serif", color: "#B91C1C", marginBottom: 20 }}>{error}</p>
          <Link href="/dashboard/orders" style={{ font: "600 14px/1 Inter Variable, sans-serif", color: "#2563EB", textDecoration: "none" }}>
            ← К заказам
          </Link>
        </div>
      </div>
    );
  }

  const d = paymentData!.bank_details;
  const statusStyle = STATUS_COLORS[status] ?? { bg: "#F1F5F9", color: "#475569" };

  return (
    <div style={{ minHeight: "100vh", background: "#FAFAFA", fontFamily: "Inter Variable, sans-serif" }}>

      {/* Header */}
      <header style={{ height: 64, background: "#ffffff", borderBottom: "1px solid #E5E7EB", padding: "0 24px", display: "flex", alignItems: "center", position: "sticky", top: 0, zIndex: 50 }}>
        <Link
          href="/"
          style={{ display: "inline-flex", alignItems: "center", gap: 8, textDecoration: "none", font: "700 20px/1 Inter Variable, sans-serif", letterSpacing: "-0.02em", color: "#111827" }}
        >
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#2563EB", flexShrink: 0 }} />
          novex
        </Link>
      </header>

      <main style={{ maxWidth: 640, margin: "0 auto", padding: "40px 20px 80px" }}>

        {/* Back + title */}
        <div style={{ marginBottom: 32 }}>
          <Link
            href="/dashboard/orders"
            style={{ display: "inline-flex", alignItems: "center", gap: 6, font: "500 13px/1 Inter Variable, sans-serif", color: "#6B7280", textDecoration: "none", marginBottom: 20 }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#111827")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#6B7280")}
          >
            <ArrowLeft size={14} />
            Назад к заказам
          </Link>
          <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
            <h1 style={{ margin: 0, font: "700 28px/1.2 Inter Variable, sans-serif", color: "#111827", letterSpacing: "-0.01em" }}>
              Оплата заказа
            </h1>
            <span style={{ display: "inline-block", padding: "5px 14px", borderRadius: 999, font: "600 13px/1 Inter Variable, sans-serif", background: statusStyle.bg, color: statusStyle.color }}>
              {STATUS_LABELS[status] ?? status}
            </span>
          </div>
          <p style={{ margin: "8px 0 0", font: "400 14px/1 Inter Variable, sans-serif", color: "#6B7280" }}>
            {paymentData!.order_reference}
          </p>
        </div>

        {/* Success modal overlay */}
        {uploadSuccess && (
          <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center", padding: "20px" }}>
            <div style={{ background: "#fff", borderRadius: 20, padding: "36px 32px", maxWidth: 420, width: "100%", textAlign: "center", boxShadow: "0 20px 60px rgba(0,0,0,0.15)" }}>
              <div style={{ width: 56, height: 56, borderRadius: "50%", background: "#F0FDF4", border: "2px solid #BBF7D0", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              </div>
              <div style={{ font: "700 18px/1.3 Inter Variable, sans-serif", color: "#111827", marginBottom: 12 }}>
                Чек успешно загружен
              </div>
              <p style={{ font: "400 14px/1.6 Inter Variable, sans-serif", color: "#6B7280", margin: "0 0 28px" }}>
                Оплата отправлена на проверку оператором. Обычно подтверждение занимает до 24 часов в рабочие дни.
              </p>
              <button
                onClick={() => router.push("/dashboard/orders")}
                style={{ width: "100%", padding: "13px 0", borderRadius: 12, border: "none", background: "#2563EB", color: "#fff", font: "600 15px/1 Inter Variable, sans-serif", cursor: "pointer" }}
              >
                OK
              </button>
            </div>
          </div>
        )}

        <>
            {/* Requisites */}
            <div style={card}>
              <div style={{ font: "700 11px/1 Inter Variable, sans-serif", color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 20 }}>
                Реквизиты для оплаты
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
                <ReqRow label="Получатель" value={d.recipient_name} />
                <ReqRow label="Банк" value={d.bank_name} />
                <ReqRow label="IBAN" value={d.iban} copy />
                <ReqRow label="БИН" value={d.bin} />
                <ReqRow label="КНП" value={d.knp} />
                <ReqRow label="Назначение платежа" value={d.purpose} copy />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 16, paddingTop: 16, borderTop: "1px solid #F1F5F9" }}>
                <span style={{ font: "400 13px/1 Inter Variable, sans-serif", color: "#6B7280" }}>Итого к оплате</span>
                <span style={{ font: "800 24px/1 Inter Variable, sans-serif", color: "#111827" }}>
                  {d.amount} {d.currency}
                </span>
              </div>
            </div>

            {/* Upload form */}
            {status !== "paid" && (
              <div style={card}>
                <div style={{ font: "700 11px/1 Inter Variable, sans-serif", color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 20 }}>
                  Подтверждение оплаты
                </div>
                <ol style={{ font: "400 13px/1.8 Inter Variable, sans-serif", color: "#6B7280", paddingLeft: 18, margin: "0 0 16px" }}>
                  <li>Переведите точную сумму по реквизитам выше.</li>
                  <li>В назначении платежа укажите номер заказа.</li>
                  <li>Сохраните скриншот или PDF-квитанцию из банка.</li>
                  <li>Загрузите файл ниже — оператор проверит оплату в течение 24 ч.</li>
                </ol>
                <p style={{ font: "400 12px/1 Inter Variable, sans-serif", color: "#9CA3AF", marginBottom: 16 }}>
                  Принимаются: JPEG, PNG, PDF. Максимальный размер: 5 МБ.
                </p>
                <form onSubmit={handleUpload} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,application/pdf"
                    required
                    style={{ font: "400 14px/1 Inter Variable, sans-serif", color: "#374151" }}
                  />
                  {uploadError && (
                    <div style={{ padding: "10px 14px", background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 10, font: "400 13px/1.4 Inter Variable, sans-serif", color: "#B91C1C" }}>
                      {uploadError}
                    </div>
                  )}
                  <button
                    type="submit"
                    disabled={uploading}
                    style={{
                      background: uploading ? "#93C5FD" : "#2563EB",
                      color: "#fff",
                      padding: "13px 24px",
                      border: "none",
                      borderRadius: 12,
                      font: "600 15px/1 Inter Variable, sans-serif",
                      cursor: uploading ? "not-allowed" : "pointer",
                      fontFamily: "inherit",
                      transition: "background 0.15s",
                      marginTop: 4,
                    }}
                    onMouseEnter={(e) => { if (!uploading) e.currentTarget.style.background = "#1D4ED8"; }}
                    onMouseLeave={(e) => { if (!uploading) e.currentTarget.style.background = "#2563EB"; }}
                  >
                    {uploading ? "Загрузка..." : "Я оплатил - загрузить чек"}
                  </button>
                </form>
              </div>
            )}
          </>
      </main>
    </div>
  );
}

function ReqRow({ label, value, copy }: { label: string; value: string; copy?: boolean }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    void navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderBottom: "1px solid #F1F5F9", gap: 12 }}>
      <span style={{ font: "400 13px/1 Inter Variable, sans-serif", color: "#6B7280", minWidth: 160, flexShrink: 0 }}>{label}</span>
      <span style={{ font: "500 14px/1.4 Inter Variable, sans-serif", color: "#111827", display: "flex", gap: 10, alignItems: "center", textAlign: "right" }}>
        {value}
        {copy && (
          <button
            onClick={handleCopy}
            style={{ background: "none", border: "1px solid #E5E7EB", borderRadius: 6, padding: "3px 8px", cursor: "pointer", color: copied ? "#166534" : "#6B7280", display: "flex", alignItems: "center", gap: 4, transition: "all 0.15s", flexShrink: 0 }}
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            <span style={{ font: "500 11px/1 Inter Variable, sans-serif" }}>{copied ? "Скопировано" : "Копировать"}</span>
          </button>
        )}
      </span>
    </div>
  );
}
