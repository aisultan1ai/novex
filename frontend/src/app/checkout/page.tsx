"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Copy, Check } from "lucide-react";

import { useAuth } from "@/components/providers/auth-provider";
import EmailVerificationNotice from "@/components/auth/EmailVerificationNotice";
import { errorMessage } from "@/lib/api/client";
import { useIsMobile } from "@/hooks/use-is-mobile";
import { ApiError, getOrderDraft, proceedToCheckout } from "@/lib/api/orders";
import {
  initiatePayment,
  getPaymentStatus,
  uploadPaymentProof,
  type PaymentData,
} from "@/lib/api/payments";
import type { OrderDraftResponse } from "@/types/order";

const STEPS = ["Данные отправления", "Отправитель", "Получатель", "Оплата"];
const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024;
const POLL_INTERVAL_MS = 5000;
const POLL_MAX_ATTEMPTS = 360;

const STATUS_LABELS: Record<string, string> = {
  awaiting_payment: "Ожидает оплаты",
  payment_under_review: "Оплата на проверке",
  paid: "Оплачено",
  dispatch_queued: "Оплачено",
  payment_rejected: "Оплата отклонена",
  cancelled: "Отменён",
};

const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  awaiting_payment:     { bg: "#FEF3C7", color: "#92400E" },
  payment_under_review: { bg: "#E6EEF7", color: "#1E40AF" },
  paid:                 { bg: "#DCFCE7", color: "#166534" },
  dispatch_queued:      { bg: "#DCFCE7", color: "#166534" },
  payment_rejected:     { bg: "#FEE2E2", color: "#991B1B" },
  cancelled:            { bg: "#F1F5F9", color: "#475569" },
};

function formatPrice(price: number, currency: string): string {
  return `${new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(price)} ${currency}`;
}

function InfoRow({ lbl, val }: { lbl: string; val: string | null | undefined }) {
  if (!val) return null;
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 12, color: "#5F6E7E", marginBottom: 3 }}>{lbl}</div>
      <div style={{ fontSize: 14, fontWeight: 600, color: "#0E1826" }}>{val}</div>
    </div>
  );
}

function Stepper({ current }: { current: number }) {
  const isMobile = useIsMobile();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: 40 }}>
      {STEPS.map((label, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", flex: i < STEPS.length - 1 ? 1 : "none" }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
              <div style={{
                width: isMobile ? 32 : 40, height: isMobile ? 32 : 40, borderRadius: "50%",
                border: done || active ? "none" : "2px solid #E2E8EE",
                background: done ? "#10B981" : active ? "#0B2545" : "#ffffff",
                display: "flex", alignItems: "center", justifyContent: "center",
                font: `700 ${isMobile ? "13px" : "15px"}/1 Inter Variable, sans-serif`,
                color: done || active ? "#ffffff" : "#9CA3AF",
                boxShadow: active ? "0 0 0 4px rgba(11,37,69,0.15)" : "none",
                flexShrink: 0, transition: "all 0.2s",
              }}>
                {done ? <Check size={isMobile ? 13 : 16} strokeWidth={3} /> : i + 1}
              </div>
              {!isMobile && (
                <span style={{ font: "500 12px/1 Inter Variable, sans-serif", color: active ? "#0E1826" : done ? "#10B981" : "#9CA3AF", whiteSpace: "nowrap" }}>
                  {label}
                </span>
              )}
            </div>
            {i < STEPS.length - 1 && (
              <div style={{ flex: 1, height: 2, background: done ? "#10B981" : "#E2E8EE", margin: "0 6px", marginBottom: isMobile ? 0 : 18, transition: "background 0.2s" }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function ReqRow({ label, value, copy: copyable }: { label: string; value: string; copy?: boolean }) {
  const isMobile = useIsMobile();
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    void navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div
      style={{
        display: "flex",
        // Phone: label above value. Side by side, a 160px label + IBAN + «Копировать»
        // is wider than the screen and pushes the whole page sideways.
        flexDirection: isMobile ? "column" : "row",
        justifyContent: "space-between",
        alignItems: isMobile ? "flex-start" : "center",
        padding: "10px 0",
        borderBottom: "1px solid #F1F5F9",
        gap: isMobile ? 6 : 12,
      }}
    >
      <span style={{ font: "400 13px/1 Inter Variable, sans-serif", color: "#5F6E7E", minWidth: isMobile ? 0 : 160, flexShrink: 0 }}>{label}</span>
      <span
        style={{
          font: "500 14px/1.4 Inter Variable, sans-serif",
          color: "#0E1826",
          display: "flex",
          gap: 10,
          alignItems: "center",
          flexWrap: "wrap",
          minWidth: 0,
          maxWidth: "100%",
          textAlign: isMobile ? "left" : "right",
          overflowWrap: "anywhere",
        }}
      >
        {value}
        {copyable && (
          <button
            onClick={handleCopy}
            style={{ background: "none", border: "1px solid #E2E8EE", borderRadius: 6, padding: "3px 8px", cursor: "pointer", color: copied ? "#166534" : "#5F6E7E", display: "flex", alignItems: "center", gap: 4, transition: "all 0.15s", flexShrink: 0 }}
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            <span style={{ font: "500 11px/1 Inter Variable, sans-serif" }}>{copied ? "Скопировано" : "Копировать"}</span>
          </button>
        )}
      </span>
    </div>
  );
}

function CheckoutPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const isMobile = useIsMobile();

  const draftId = useMemo(() => {
    const raw = searchParams.get("draftId");
    if (!raw) return null;
    const n = Number(raw);
    return Number.isInteger(n) && n > 0 ? n : null;
  }, [searchParams]);

  // Draft state
  const [draft, setDraft] = useState<OrderDraftResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Unverified customers get 403 {code: "email_not_verified"} from checkout /
  // payment — show a dedicated «подтвердите email» panel instead of a raw error.
  const [needsEmailVerify, setNeedsEmailVerify] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  // View: "summary" → show order details + pay button; "payment" → show bank details + upload
  const [view, setView] = useState<"summary" | "payment">("summary");
  const [isPaying, setIsPaying] = useState(false);

  // Payment state
  const [paymentData, setPaymentData] = useState<PaymentData | null>(null);
  const [status, setStatus] = useState<string>("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollAttemptsRef = useRef(0);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push(`/login?next=/checkout?draftId=${draftId ?? ""}`);
    }
  }, [isAuthenticated, authLoading, draftId, router]);

  useEffect(() => {
    if (!isAuthenticated || !draftId) return;
    async function load() {
      setIsLoading(true);
      setError(null);
      setNeedsEmailVerify(false);
      try {
        let data = await getOrderDraft(draftId!);
        if (data.status === "shipment_details_completed") {
          data = await proceedToCheckout(draftId!);
        }
        if (data.status === "paid") {
          router.replace("/dashboard/orders");
          return;
        }
        setDraft(data);
        // If payment already initiated (e.g. user returning after leaving), skip straight to payment view
        if (data.status === "awaiting_payment" || data.status === "payment_rejected") {
          const payment = await initiatePayment(String(draftId!));
          setPaymentData(payment);
          setStatus(payment.status);
          setView("payment");
        }
      } catch (err) {
        if (err instanceof ApiError && err.code === "email_not_verified") {
          setNeedsEmailVerify(true);
        } else {
          setError(errorMessage(err, "Не удалось загрузить заказ."));
        }
      } finally {
        setIsLoading(false);
      }
    }
    void load();
  }, [isAuthenticated, draftId, router, reloadKey]);

  useEffect(() => {
    if (!uploadSuccess || !draftId) return;
    pollAttemptsRef.current = 0;
    pollingRef.current = setInterval(async () => {
      pollAttemptsRef.current += 1;
      if (pollAttemptsRef.current >= POLL_MAX_ATTEMPTS) {
        clearInterval(pollingRef.current!);
        return;
      }
      const s = await getPaymentStatus(String(draftId));
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
  }, [uploadSuccess, draftId, router]);

  async function handlePay() {
    if (!draftId || !draft) return;
    setIsPaying(true);
    setError(null);
    try {
      const data = await initiatePayment(String(draftId));
      setPaymentData(data);
      setStatus(data.status);
      setView("payment");
    } catch (err) {
      if (err instanceof ApiError && err.code === "email_not_verified") {
        setNeedsEmailVerify(true);
      } else {
        setError(errorMessage(err, "Не удалось начать оплату. Попробуйте ещё раз."));
      }
    } finally {
      setIsPaying(false);
    }
  }

  const handleUpload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const file = selectedFile ?? fileInputRef.current?.files?.[0];
    if (!file || !paymentData) return;
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setUploadError("Файл слишком большой. Максимальный размер: 5 МБ.");
      return;
    }
    setUploading(true);
    setUploadError(null);
    try {
      await uploadPaymentProof(String(draftId), paymentData.payment_id, file);
      setUploadSuccess(true);
      setStatus("payment_under_review");
    } catch (err) {
      setUploadError(errorMessage(err, "Не удалось загрузить файл. Попробуйте ещё раз."));
    } finally {
      setUploading(false);
    }
  };

  if (authLoading || (!isAuthenticated && !authLoading)) return null;

  const card = {
    background: "#ffffff",
    border: "1px solid #E2E8EE",
    borderRadius: 16,
    boxShadow: "0 2px 8px rgba(17,24,39,0.04)",
  };

  const sender = draft?.sender;
  const recipient = draft?.recipient;
  const statusStyle = STATUS_COLORS[status] ?? { bg: "#F1F5F9", color: "#475569" };

  return (
    <div style={{ minHeight: "100vh", background: "#FAFAFA", fontFamily: "Inter Variable, sans-serif" }}>

      {/* Header */}
      <header style={{ height: 64, background: "#ffffff", borderBottom: "1px solid #E2E8EE", padding: "0 24px", display: "flex", alignItems: "center", position: "sticky", top: 0, zIndex: 50 }}>
        <Link
          href="/"
          aria-label="Novex — на главную"
          style={{ display: "inline-flex", alignItems: "center", gap: 8, textDecoration: "none", font: "700 20px/1 'Space Grotesk Variable', 'Inter Variable', sans-serif", letterSpacing: "-0.02em", color: "#0E1826" }}
        >
          <svg width="30" height="27" viewBox="10 11 38 34" fill="none" aria-hidden="true" style={{ flexShrink: 0, display: "block" }}>
            <circle cx="17" cy="28" r="5" fill="#22C9E0" />
            <line x1="20" y1="25.5" x2="37" y2="17" stroke="#3E6E8A" strokeWidth="2.2" strokeLinecap="round" />
            <line x1="21" y1="28" x2="38" y2="28" stroke="#22C9E0" strokeWidth="2.4" strokeLinecap="round" />
            <line x1="20" y1="30.5" x2="37" y2="39" stroke="#3E6E8A" strokeWidth="2.2" strokeLinecap="round" />
            <circle cx="40" cy="16" r="3.4" fill="#3E6E8A" />
            <circle cx="41" cy="28" r="4.6" fill="#22C9E0" />
            <circle cx="40" cy="40" r="3.4" fill="#3E6E8A" />
          </svg>
          <span>n<span style={{ color: "#22C9E0" }}>o</span>vex</span>
        </Link>
      </header>

      {/* Upload success overlay */}
      {uploadSuccess && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center", padding: "20px" }}>
          <div style={{ background: "#fff", borderRadius: 20, padding: "36px 32px", maxWidth: 420, width: "100%", textAlign: "center", boxShadow: "0 20px 60px rgba(0,0,0,0.15)" }}>
            <div style={{ width: 56, height: 56, borderRadius: "50%", background: "#F0FDF4", border: "2px solid #BBF7D0", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <div style={{ font: "700 18px/1.3 Inter Variable, sans-serif", color: "#0E1826", marginBottom: 12 }}>
              Чек успешно загружен
            </div>
            <p style={{ font: "400 14px/1.6 Inter Variable, sans-serif", color: "#5F6E7E", margin: "0 0 28px" }}>
              Оплата отправлена на проверку оператором.
            </p>
            <button
              onClick={() => router.push("/dashboard/orders")}
              style={{ width: "100%", padding: "13px 0", borderRadius: 12, border: "none", background: "#0B2545", color: "#fff", font: "600 15px/1 Inter Variable, sans-serif", cursor: "pointer" }}
            >
              OK
            </button>
          </div>
        </div>
      )}

      <main style={{ maxWidth: 780, margin: "0 auto", padding: isMobile ? "24px 16px 80px" : "40px 24px 80px" }}>

        {/* Back + title */}
        <div style={{ marginBottom: 32 }}>
          <Link
            href="/dashboard/orders"
            style={{ display: "inline-flex", alignItems: "center", gap: 6, font: "500 13px/1 Inter Variable, sans-serif", color: "#5F6E7E", textDecoration: "none", marginBottom: 20 }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#0E1826")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#5F6E7E")}
          >
            <ArrowLeft size={14} />
            Мои заказы
          </Link>
          <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
            <h1 style={{ margin: 0, font: "700 28px/1.2 'Space Grotesk Variable', 'Inter Variable', sans-serif", color: "#0E1826", letterSpacing: "-0.01em" }}>
              Оформление оплаты
            </h1>
            {view === "payment" && status && (
              <span style={{ display: "inline-block", padding: "5px 14px", borderRadius: 999, font: "600 13px/1 Inter Variable, sans-serif", background: statusStyle.bg, color: statusStyle.color }}>
                {STATUS_LABELS[status] ?? status}
              </span>
            )}
          </div>
          <p style={{ margin: "6px 0 0", font: "400 15px/1 Inter Variable, sans-serif", color: "#5F6E7E" }}>
            {view === "summary"
              ? "Проверьте данные и подтвердите заказ"
              : (paymentData?.order_reference ?? "Переведите оплату по реквизитам ниже")}
          </p>
        </div>

        {/* Stepper - step 4 (Оплата) active, 1-3 completed */}
        <Stepper current={3} />

        {isLoading ? (
          <div style={{ ...card, padding: 48, textAlign: "center", color: "#5F6E7E", font: "400 14px/1 Inter Variable, sans-serif" }}>
            Загружаем заказ…
          </div>
        ) : needsEmailVerify ? (
          <EmailVerificationNotice variant="card" onVerified={() => setReloadKey((k) => k + 1)} />
        ) : error && !draft ? (
          <div style={{ ...card, padding: 28 }}>
            <div style={{ background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 10, padding: "14px 16px", color: "#B91C1C", font: "400 14px/1.4 Inter Variable, sans-serif", marginBottom: 16 }}>
              {error}
            </div>
            <Link
              href="/"
              style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "10px 20px", borderRadius: 10, border: "1px solid #E2E8EE", background: "#ffffff", font: "600 14px/1 Inter Variable, sans-serif", color: "#374151", textDecoration: "none" }}
            >
              ← Новый расчёт тарифа
            </Link>
          </div>
        ) : view === "summary" && draft ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            {/* Route & carrier */}
            <div style={{ ...card, padding: isMobile ? "20px 16px" : "24px 28px" }}>
              <div style={{ font: "700 11px/1 Inter Variable, sans-serif", color: "#5F6E7E", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 16 }}>
                Маршрут и тариф
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16 }}>
                <div>
                  <div style={{ font: "700 22px/1.2 Inter Variable, sans-serif", color: "#0E1826", marginBottom: 8 }}>
                    {draft.from_city_snapshot} → {draft.to_city_snapshot}
                  </div>
                  <div style={{ font: "400 13px/1.6 Inter Variable, sans-serif", color: "#5F6E7E" }}>
                    {draft.shipment_type_snapshot} · {draft.eta_days_min_snapshot}-{draft.eta_days_max_snapshot} дн.
                  </div>
                  <div style={{ font: "400 13px/1 Inter Variable, sans-serif", color: "#5F6E7E", marginTop: 4 }}>
                    {draft.carrier_name_snapshot} - {draft.tariff_name_snapshot}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ font: "800 30px/1 'Space Grotesk Variable', 'Inter Variable', sans-serif", color: "#0E1826" }}>
                    {formatPrice(Number(draft.price_snapshot), draft.currency_snapshot)}
                  </div>
                  <div style={{ font: "400 12px/1 Inter Variable, sans-serif", color: "#5F6E7E", marginTop: 6 }}>
                    стоимость доставки
                  </div>
                </div>
              </div>
            </div>

            {/* Sender + Recipient */}
            <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: 16 }}>
              <div style={{ ...card, padding: isMobile ? "20px 16px" : "24px 28px" }}>
                <div style={{ font: "700 11px/1 Inter Variable, sans-serif", color: "#5F6E7E", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 16 }}>
                  Отправитель
                </div>
                <InfoRow lbl="ФИО" val={sender?.full_name} />
                <InfoRow lbl="Телефон" val={sender?.phone} />
                <InfoRow lbl="Email" val={sender?.email} />
                <InfoRow lbl="Компания" val={sender?.company_name} />
                <InfoRow lbl="Адрес" val={[sender?.country, sender?.city, sender?.address_line1, sender?.address_line2].filter(Boolean).join(", ")} />
                <InfoRow lbl="Почтовый индекс" val={sender?.postal_code} />
                <InfoRow lbl="Комментарий" val={sender?.comment} />
              </div>
              <div style={{ ...card, padding: isMobile ? "20px 16px" : "24px 28px" }}>
                <div style={{ font: "700 11px/1 Inter Variable, sans-serif", color: "#5F6E7E", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 16 }}>
                  Получатель
                </div>
                <InfoRow lbl="ФИО" val={recipient?.full_name} />
                <InfoRow lbl="Телефон" val={recipient?.phone} />
                <InfoRow lbl="Email" val={recipient?.email} />
                <InfoRow lbl="Компания" val={recipient?.company_name} />
                <InfoRow lbl="Адрес" val={[recipient?.country, recipient?.city, recipient?.address_line1, recipient?.address_line2].filter(Boolean).join(", ")} />
                <InfoRow lbl="Почтовый индекс" val={recipient?.postal_code} />
                <InfoRow lbl="Комментарий" val={recipient?.comment} />
              </div>
            </div>

            {/* Packages */}
            <div style={{ ...card, padding: isMobile ? "20px 16px" : "24px 28px" }}>
              <div style={{ font: "700 11px/1 Inter Variable, sans-serif", color: "#5F6E7E", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 16 }}>
                Грузовые места ({draft.packages.length})
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {draft.packages.map((pkg, i) => (
                  <div
                    key={pkg.id}
                    style={{ display: "flex", justifyContent: "space-between", padding: "12px 16px", background: "#F8FAFC", borderRadius: 12, font: "400 14px/1 Inter Variable, sans-serif", flexWrap: "wrap", gap: 8 }}
                  >
                    <span style={{ fontWeight: 600, color: "#0E1826" }}>
                      {i + 1}. {pkg.description}
                    </span>
                    <span style={{ color: "#5F6E7E" }}>
                      {pkg.quantity} шт · {Number(pkg.weight_kg)} кг · {Number(pkg.width_cm)}×{Number(pkg.height_cm)}×{Number(pkg.depth_cm)} см
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Payment CTA */}
            <div style={{ ...card, padding: isMobile ? "20px 16px" : "24px 28px" }}>
              <div style={{ font: "700 11px/1 Inter Variable, sans-serif", color: "#5F6E7E", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 16 }}>
                Способ оплаты
              </div>
              <div style={{ padding: "14px 18px", background: "#F1F5F9", border: "1px solid #CFDCEA", borderRadius: 12, font: "400 13px/1.5 Inter Variable, sans-serif", color: "#1E40AF", marginBottom: 24 }}>
                <strong>Банковский перевод.</strong> После нажатия кнопки вы получите реквизиты и сможете загрузить подтверждение оплаты.
              </div>
              {error && (
                <div style={{ padding: "12px 16px", background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 10, font: "400 13px/1.4 Inter Variable, sans-serif", color: "#B91C1C", marginBottom: 20 }}>
                  {error}
                </div>
              )}
              <div style={{ display: "flex", flexDirection: isMobile ? "column" : "row", justifyContent: "space-between", alignItems: isMobile ? "stretch" : "center", gap: 16 }}>
                <div>
                  <div style={{ font: "400 13px/1 Inter Variable, sans-serif", color: "#5F6E7E", marginBottom: 6 }}>Итого к оплате</div>
                  <div style={{ font: "800 28px/1 'Space Grotesk Variable', 'Inter Variable', sans-serif", color: "#0E1826" }}>
                    {formatPrice(Number(draft.price_snapshot), draft.currency_snapshot)}
                  </div>
                </div>
                <button
                  onClick={() => void handlePay()}
                  disabled={isPaying}
                  style={{
                    background: isPaying ? "#94A6C0" : "#0B2545",
                    color: "#fff",
                    border: "none",
                    borderRadius: 12,
                    padding: "14px 32px",
                    font: "600 15px/1 Inter Variable, sans-serif",
                    cursor: isPaying ? "not-allowed" : "pointer",
                    fontFamily: "inherit",
                    width: isMobile ? "100%" : "auto",
                    minWidth: isMobile ? "auto" : 220,
                    transition: "background 0.15s",
                  }}
                  onMouseEnter={(e) => { if (!isPaying) e.currentTarget.style.background = "#0E2E5C"; }}
                  onMouseLeave={(e) => { if (!isPaying) e.currentTarget.style.background = "#0B2545"; }}
                >
                  {isPaying ? "Обрабатываем…" : `Оплатить ${formatPrice(Number(draft.price_snapshot), draft.currency_snapshot)}`}
                </button>
              </div>
            </div>

          </div>
        ) : view === "payment" && paymentData ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            {/* Bank details */}
            <div style={{ ...card, padding: isMobile ? "20px 16px" : "24px 28px" }}>
              <div style={{ font: "700 11px/1 Inter Variable, sans-serif", color: "#5F6E7E", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 20 }}>
                Реквизиты для оплаты
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
                <ReqRow label="Получатель" value={paymentData.bank_details.recipient_name} />
                <ReqRow label="Банк" value={paymentData.bank_details.bank_name} />
                <ReqRow label="IBAN" value={paymentData.bank_details.iban} copy />
                <ReqRow label="БИН" value={paymentData.bank_details.bin} />
                <ReqRow label="КНП" value={paymentData.bank_details.knp} />
                <ReqRow label="Назначение платежа" value={paymentData.bank_details.purpose} copy />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 16, paddingTop: 16, borderTop: "1px solid #F1F5F9" }}>
                <span style={{ font: "400 13px/1 Inter Variable, sans-serif", color: "#5F6E7E" }}>Итого к оплате</span>
                <span style={{ font: "800 24px/1 'Space Grotesk Variable', 'Inter Variable', sans-serif", color: "#0E1826" }}>
                  {paymentData.bank_details.amount} {paymentData.bank_details.currency}
                </span>
              </div>
            </div>

            {/* Upload proof */}
            {status !== "paid" && status !== "dispatch_queued" && (
              <div style={{ ...card, padding: isMobile ? "20px 16px" : "24px 28px" }}>
                <div style={{ font: "700 11px/1 Inter Variable, sans-serif", color: "#5F6E7E", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 20 }}>
                  Подтверждение оплаты
                </div>
                <ol style={{ font: "400 13px/1.8 Inter Variable, sans-serif", color: "#5F6E7E", paddingLeft: 18, margin: "0 0 16px" }}>
                  <li>Переведите точную сумму по реквизитам выше.</li>
                  <li>В назначении платежа укажите номер заказа.</li>
                  <li>Сохраните скриншот или PDF-квитанцию из банка.</li>
                  <li>Загрузите файл ниже - оператор проверит оплату.</li>
                </ol>
                <p style={{ font: "400 12px/1 Inter Variable, sans-serif", color: "#9CA3AF", marginBottom: 16 }}>
                  Принимаются: JPEG, PNG, PDF. Максимальный размер: 5 МБ.
                </p>
                <form onSubmit={(e) => void handleUpload(e)} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {/* Hidden native input - controlled via the styled label below. */}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,application/pdf"
                    required
                    style={{ display: "none" }}
                    onChange={(e) => {
                      const f = e.target.files?.[0] ?? null;
                      if (f && f.size > MAX_FILE_SIZE_BYTES) {
                        setUploadError("Файл слишком большой. Максимальный размер: 5 МБ.");
                        setSelectedFile(null);
                        if (fileInputRef.current) fileInputRef.current.value = "";
                        return;
                      }
                      setSelectedFile(f);
                      setUploadError(null);
                    }}
                  />
                  {!selectedFile ? (
                    <label
                      htmlFor="__none"
                      onClick={() => fileInputRef.current?.click()}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 10,
                        padding: "18px 16px",
                        border: "2px dashed #CBD5E1",
                        borderRadius: 12,
                        background: "#F8FAFC",
                        cursor: "pointer",
                        color: "#475569",
                        font: "500 14px/1.2 Inter Variable, sans-serif",
                        transition: "background 0.15s, border-color 0.15s",
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "#F1F5F9"; e.currentTarget.style.borderColor = "#94A3B8"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "#F8FAFC"; e.currentTarget.style.borderColor = "#CBD5E1"; }}
                    >
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="17 8 12 3 7 8" />
                        <line x1="12" y1="3" x2="12" y2="15" />
                      </svg>
                      Выбрать файл
                    </label>
                  ) : (
                    <div style={{
                      display: "flex", alignItems: "center", gap: 10,
                      padding: "12px 14px",
                      border: "1px solid #BBF7D0",
                      background: "#F0FDF4",
                      borderRadius: 12,
                    }}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ font: "600 13px/1.3 Inter Variable, sans-serif", color: "#166534", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {selectedFile.name}
                        </div>
                        <div style={{ font: "400 11px/1.3 Inter Variable, sans-serif", color: "#4B5563", marginTop: 2 }}>
                          {(selectedFile.size / 1024).toFixed(0)} КБ · готов к отправке
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedFile(null);
                          if (fileInputRef.current) fileInputRef.current.value = "";
                        }}
                        style={{
                          background: "transparent", border: "none", color: "#64748b",
                          cursor: "pointer", padding: 4, fontFamily: "inherit",
                          font: "500 12px/1 Inter Variable, sans-serif",
                          flexShrink: 0,
                        }}
                      >
                        Заменить
                      </button>
                    </div>
                  )}
                  {uploadError && (
                    <div style={{ padding: "10px 14px", background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 10, font: "400 13px/1.4 Inter Variable, sans-serif", color: "#B91C1C" }}>
                      {uploadError}
                    </div>
                  )}
                  <button
                    type="submit"
                    disabled={uploading || !selectedFile}
                    style={{
                      background: uploading ? "#94A6C0" : !selectedFile ? "#E2E8EE" : "#0B2545",
                      color: !selectedFile && !uploading ? "#9CA3AF" : "#fff",
                      padding: "13px 24px",
                      border: "none",
                      borderRadius: 12,
                      font: "600 15px/1 Inter Variable, sans-serif",
                      cursor: (uploading || !selectedFile) ? "not-allowed" : "pointer",
                      fontFamily: "inherit",
                      transition: "background 0.15s",
                      marginTop: 4,
                    }}
                    onMouseEnter={(e) => { if (!uploading && selectedFile) e.currentTarget.style.background = "#0E2E5C"; }}
                    onMouseLeave={(e) => { if (!uploading && selectedFile) e.currentTarget.style.background = "#0B2545"; }}
                  >
                    {uploading ? "Загрузка..." : "Я оплатил - загрузить чек"}
                  </button>
                </form>
              </div>
            )}

          </div>
        ) : null}
      </main>
    </div>
  );
}

export default function CheckoutPage() {
  return <Suspense><CheckoutPageInner /></Suspense>;
}
