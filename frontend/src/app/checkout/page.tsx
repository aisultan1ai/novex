"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { useAuth } from "@/components/providers/auth-provider";
import { useIsMobile } from "@/hooks/use-is-mobile";
import { ApiError, getOrderDraft, proceedToCheckout } from "@/lib/api/orders";
import type { OrderDraftResponse } from "@/types/order";

function formatPrice(price: number, currency: string): string {
  return `${new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(price)} ${currency}`;
}

function InfoRow({ lbl, val }: { lbl: string; val: string | null | undefined }) {
  if (!val) return null;
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 12, color: "#6B7280", marginBottom: 3 }}>{lbl}</div>
      <div style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>{val}</div>
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

  const [draft, setDraft] = useState<OrderDraftResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPaying] = useState(false);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push(`/login?next=/checkout?draftId=${draftId ?? ""}`);
    }
  }, [isAuthenticated, authLoading, draftId, router]);

  useEffect(() => {
    if (!isAuthenticated || !draftId) return;

    async function load() {
      setIsLoading(true);
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
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "Не удалось загрузить заказ.");
      } finally {
        setIsLoading(false);
      }
    }

    void load();
  }, [isAuthenticated, draftId, router]);

  function handlePay() {
    if (!draftId || !draft) return;
    router.push(`/checkout/payment?orderId=${draftId}`);
  }

  if (authLoading || (!isAuthenticated && !authLoading)) return null;

  const sender = draft?.sender;
  const recipient = draft?.recipient;

  const card = {
    background: "#ffffff",
    border: "1px solid #E5E7EB",
    borderRadius: 16,
    boxShadow: "0 2px 8px rgba(17,24,39,0.04)",
  };

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

      <main style={{ maxWidth: 780, margin: "0 auto", padding: isMobile ? "24px 16px 80px" : "40px 24px 80px" }}>

        {/* Back + title */}
        <div style={{ marginBottom: 32 }}>
          <Link
            href="/dashboard/orders"
            style={{ display: "inline-flex", alignItems: "center", gap: 6, font: "500 13px/1 Inter Variable, sans-serif", color: "#6B7280", textDecoration: "none", marginBottom: 20 }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#111827")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#6B7280")}
          >
            <ArrowLeft size={14} />
            Мои заказы
          </Link>
          <h1 style={{ margin: 0, font: "700 28px/1.2 Inter Variable, sans-serif", color: "#111827", letterSpacing: "-0.01em" }}>
            Оформление оплаты
          </h1>
          <p style={{ margin: "6px 0 0", font: "400 15px/1 Inter Variable, sans-serif", color: "#6B7280" }}>
            Проверьте данные и подтвердите заказ
          </p>
        </div>

        {isLoading ? (
          <div style={{ ...card, padding: 48, textAlign: "center", color: "#6B7280", font: "400 14px/1 Inter Variable, sans-serif" }}>
            Загружаем заказ…
          </div>
        ) : error && !draft ? (
          <div style={{ ...card, padding: 28 }}>
            <div style={{ background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 10, padding: "14px 16px", color: "#B91C1C", font: "400 14px/1.4 Inter Variable, sans-serif", marginBottom: 16 }}>
              {error}
            </div>
            <Link
              href="/"
              style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "10px 20px", borderRadius: 10, border: "1px solid #E5E7EB", background: "#ffffff", font: "600 14px/1 Inter Variable, sans-serif", color: "#374151", textDecoration: "none" }}
            >
              ← Новый расчёт тарифа
            </Link>
          </div>
        ) : draft ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            {/* Route & carrier */}
            <div style={{ ...card, padding: "24px 28px" }}>
              <div style={{ font: "700 11px/1 Inter Variable, sans-serif", color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 16 }}>
                Маршрут и тариф
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16 }}>
                <div>
                  <div style={{ font: "700 22px/1.2 Inter Variable, sans-serif", color: "#111827", marginBottom: 8 }}>
                    {draft.from_city_snapshot} → {draft.to_city_snapshot}
                  </div>
                  <div style={{ font: "400 13px/1.6 Inter Variable, sans-serif", color: "#6B7280" }}>
                    {draft.shipment_type_snapshot} · {draft.eta_days_min_snapshot}-{draft.eta_days_max_snapshot} дн.
                  </div>
                  <div style={{ font: "400 13px/1 Inter Variable, sans-serif", color: "#6B7280", marginTop: 4 }}>
                    {draft.carrier_name_snapshot} - {draft.tariff_name_snapshot}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ font: "800 30px/1 Inter Variable, sans-serif", color: "#111827" }}>
                    {formatPrice(Number(draft.price_snapshot), draft.currency_snapshot)}
                  </div>
                  <div style={{ font: "400 12px/1 Inter Variable, sans-serif", color: "#6B7280", marginTop: 6 }}>
                    стоимость доставки
                  </div>
                </div>
              </div>
            </div>

            {/* Sender + Recipient */}
            <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", gap: 16 }}>
              <div style={{ ...card, padding: "24px 28px" }}>
                <div style={{ font: "700 11px/1 Inter Variable, sans-serif", color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 16 }}>
                  Отправитель
                </div>
                <InfoRow lbl="ФИО" val={sender?.full_name} />
                <InfoRow lbl="Телефон" val={sender?.phone} />
                <InfoRow lbl="Email" val={sender?.email} />
                <InfoRow lbl="Компания" val={sender?.company_name} />
                <InfoRow
                  lbl="Адрес"
                  val={[sender?.country, sender?.city, sender?.address_line1, sender?.address_line2].filter(Boolean).join(", ")}
                />
                <InfoRow lbl="Почтовый индекс" val={sender?.postal_code} />
                <InfoRow lbl="Комментарий" val={sender?.comment} />
              </div>

              <div style={{ ...card, padding: "24px 28px" }}>
                <div style={{ font: "700 11px/1 Inter Variable, sans-serif", color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 16 }}>
                  Получатель
                </div>
                <InfoRow lbl="ФИО" val={recipient?.full_name} />
                <InfoRow lbl="Телефон" val={recipient?.phone} />
                <InfoRow lbl="Email" val={recipient?.email} />
                <InfoRow lbl="Компания" val={recipient?.company_name} />
                <InfoRow
                  lbl="Адрес"
                  val={[recipient?.country, recipient?.city, recipient?.address_line1, recipient?.address_line2].filter(Boolean).join(", ")}
                />
                <InfoRow lbl="Почтовый индекс" val={recipient?.postal_code} />
                <InfoRow lbl="Комментарий" val={recipient?.comment} />
              </div>
            </div>

            {/* Packages */}
            <div style={{ ...card, padding: "24px 28px" }}>
              <div style={{ font: "700 11px/1 Inter Variable, sans-serif", color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 16 }}>
                Грузовые места ({draft.packages.length})
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {draft.packages.map((pkg, i) => (
                  <div
                    key={pkg.id}
                    style={{ display: "flex", justifyContent: "space-between", padding: "12px 16px", background: "#F8FAFC", borderRadius: 12, font: "400 14px/1 Inter Variable, sans-serif", flexWrap: "wrap", gap: 8 }}
                  >
                    <span style={{ fontWeight: 600, color: "#111827" }}>
                      {i + 1}. {pkg.description}
                    </span>
                    <span style={{ color: "#6B7280" }}>
                      {pkg.quantity} шт · {Number(pkg.weight_kg)} кг · {Number(pkg.width_cm)}×{Number(pkg.height_cm)}×{Number(pkg.depth_cm)} см
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Payment section */}
            <div style={{ ...card, padding: "24px 28px" }}>
              <div style={{ font: "700 11px/1 Inter Variable, sans-serif", color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 16 }}>
                Способ оплаты
              </div>

              <div style={{ padding: "14px 18px", background: "#EFF6FF", border: "1px solid #BFDBFE", borderRadius: 12, font: "400 13px/1.5 Inter Variable, sans-serif", color: "#1E40AF", marginBottom: 24 }}>
                <strong>Банковский перевод.</strong> После нажатия кнопки вы получите реквизиты и сможете загрузить подтверждение оплаты.
              </div>

              {error && (
                <div style={{ padding: "12px 16px", background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 10, font: "400 13px/1.4 Inter Variable, sans-serif", color: "#B91C1C", marginBottom: 20 }}>
                  {error}
                </div>
              )}

              <div style={{ display: "flex", flexDirection: isMobile ? "column" : "row", justifyContent: "space-between", alignItems: isMobile ? "stretch" : "center", gap: 16 }}>
                <div>
                  <div style={{ font: "400 13px/1 Inter Variable, sans-serif", color: "#6B7280", marginBottom: 6 }}>Итого к оплате</div>
                  <div style={{ font: "800 28px/1 Inter Variable, sans-serif", color: "#111827" }}>
                    {formatPrice(Number(draft.price_snapshot), draft.currency_snapshot)}
                  </div>
                </div>
                <button
                  onClick={() => void handlePay()}
                  disabled={isPaying}
                  style={{
                    background: isPaying ? "#93C5FD" : "#2563EB",
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
                  onMouseEnter={(e) => { if (!isPaying) e.currentTarget.style.background = "#1D4ED8"; }}
                  onMouseLeave={(e) => { if (!isPaying) e.currentTarget.style.background = "#2563EB"; }}
                >
                  {isPaying ? "Обрабатываем…" : `Оплатить ${formatPrice(Number(draft.price_snapshot), draft.currency_snapshot)}`}
                </button>
              </div>
            </div>

          </div>
        ) : null}
      </main>
    </div>
  );
}

export default function CheckoutPage() {
  return <Suspense><CheckoutPageInner /></Suspense>;
}
