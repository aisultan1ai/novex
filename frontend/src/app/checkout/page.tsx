"use client";

import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import {
  ApiError,
  getOrderDraft,
  mockPayOrderDraft,
  proceedToCheckout,
} from "@/lib/api/orders";
import type { OrderDraftResponse } from "@/types/order";

// ─── Styles ──────────────────────────────────────────────────────────────────

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  background: "#f8fafc",
  padding: "32px 20px 80px",
  fontFamily:
    "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  color: "#0f172a",
};

const containerStyle: CSSProperties = {
  maxWidth: 780,
  margin: "0 auto",
};

const card: CSSProperties = {
  background: "#ffffff",
  border: "1px solid #e5e7eb",
  borderRadius: 16,
  boxShadow: "0 2px 12px rgba(15,23,42,0.05)",
};

const sectionTitle: CSSProperties = {
  fontSize: 13,
  fontWeight: 700,
  color: "#94a3b8",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  margin: "0 0 14px",
};

const label: CSSProperties = {
  fontSize: 12,
  color: "#94a3b8",
  marginBottom: 3,
};

const value: CSSProperties = {
  fontSize: 14,
  fontWeight: 600,
  color: "#0f172a",
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

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
      <div style={label}>{lbl}</div>
      <div style={value}>{val}</div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CheckoutPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const draftId = useMemo(() => {
    const raw = searchParams.get("draftId");
    if (!raw) return null;
    const n = Number(raw);
    return Number.isInteger(n) && n > 0 ? n : null;
  }, [searchParams]);

  const [draft, setDraft] = useState<OrderDraftResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPaying, setIsPaying] = useState(false);

  // Auth guard
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push(`/login?next=/checkout?draftId=${draftId ?? ""}`);
    }
  }, [isAuthenticated, authLoading, draftId, router]);

  // Load draft
  useEffect(() => {
    if (!isAuthenticated || !draftId) return;

    async function load() {
      setIsLoading(true);
      try {
        let data = await getOrderDraft(draftId!);

        // If still in shipment_details_completed → move to ready_for_checkout
        if (data.status === "shipment_details_completed") {
          data = await proceedToCheckout(draftId!);
        }

        // If already paid — redirect straight to orders
        if (data.status === "paid") {
          router.replace("/dashboard/orders");
          return;
        }

        setDraft(data);
      } catch (err) {
        setError(
          err instanceof ApiError ? err.detail : "Не удалось загрузить заказ.",
        );
      } finally {
        setIsLoading(false);
      }
    }

    void load();
  }, [isAuthenticated, draftId, router]);

  async function handlePay() {
    if (!draftId || !draft) return;
    setIsPaying(true);
    setError(null);
    try {
      await mockPayOrderDraft(draftId);
      router.push("/dashboard/orders?paid=1");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail : "Ошибка при оплате. Попробуйте снова.",
      );
      setIsPaying(false);
    }
  }

  if (authLoading || (!isAuthenticated && !authLoading)) return null;

  const sender = draft?.sender;
  const recipient = draft?.recipient;

  return (
    <main style={pageStyle}>
      <div style={containerStyle}>

        {/* Header */}
        <div style={{ marginBottom: 28 }}>
          <button
            onClick={() => router.push("/dashboard/orders")}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              fontSize: 14,
              color: "#64748b",
              padding: 0,
              marginBottom: 16,
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontFamily: "inherit",
            }}
          >
            ← Мои заказы
          </button>
          <h1 style={{ margin: 0, fontSize: 26, fontWeight: 800 }}>
            Оформление оплаты
          </h1>
          <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>
            Проверьте данные и подтвердите заказ
          </p>
        </div>

        {isLoading ? (
          <div style={{ ...card, padding: 40, textAlign: "center", color: "#64748b", fontSize: 14 }}>
            Загружаем заказ…
          </div>
        ) : error && !draft ? (
          <div style={{ ...card, padding: 24, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 14 }}>
            {error}
          </div>
        ) : draft ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            {/* Route & carrier */}
            <div style={{ ...card, padding: "20px 24px" }}>
              <p style={sectionTitle}>Маршрут и тариф</p>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16 }}>
                <div>
                  <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 6 }}>
                    {draft.from_city_snapshot} → {draft.to_city_snapshot}
                  </div>
                  <div style={{ fontSize: 13, color: "#64748b" }}>
                    {draft.shipment_type_snapshot} · {draft.eta_days_min_snapshot}–{draft.eta_days_max_snapshot} дн.
                  </div>
                  <div style={{ fontSize: 13, color: "#64748b", marginTop: 4 }}>
                    {draft.carrier_name_snapshot} — {draft.tariff_name_snapshot}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: 28, fontWeight: 800, color: "#0f172a" }}>
                    {formatPrice(Number(draft.price_snapshot), draft.currency_snapshot)}
                  </div>
                  <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 2 }}>
                    стоимость доставки
                  </div>
                </div>
              </div>
            </div>

            {/* Sender + Recipient */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div style={{ ...card, padding: "20px 24px" }}>
                <p style={sectionTitle}>Отправитель</p>
                <InfoRow lbl="ФИО" val={sender?.full_name} />
                <InfoRow lbl="Телефон" val={sender?.phone} />
                <InfoRow lbl="Email" val={sender?.email} />
                <InfoRow lbl="Компания" val={sender?.company_name} />
                <InfoRow
                  lbl="Адрес"
                  val={[sender?.country, sender?.city, sender?.address_line1, sender?.address_line2]
                    .filter(Boolean)
                    .join(", ")}
                />
                <InfoRow lbl="Почтовый индекс" val={sender?.postal_code} />
                <InfoRow lbl="Комментарий" val={sender?.comment} />
              </div>

              <div style={{ ...card, padding: "20px 24px" }}>
                <p style={sectionTitle}>Получатель</p>
                <InfoRow lbl="ФИО" val={recipient?.full_name} />
                <InfoRow lbl="Телефон" val={recipient?.phone} />
                <InfoRow lbl="Email" val={recipient?.email} />
                <InfoRow lbl="Компания" val={recipient?.company_name} />
                <InfoRow
                  lbl="Адрес"
                  val={[recipient?.country, recipient?.city, recipient?.address_line1, recipient?.address_line2]
                    .filter(Boolean)
                    .join(", ")}
                />
                <InfoRow lbl="Почтовый индекс" val={recipient?.postal_code} />
                <InfoRow lbl="Комментарий" val={recipient?.comment} />
              </div>
            </div>

            {/* Packages */}
            <div style={{ ...card, padding: "20px 24px" }}>
              <p style={sectionTitle}>
                Грузовые места ({draft.packages.length})
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {draft.packages.map((pkg, i) => (
                  <div
                    key={pkg.id}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "12px 16px",
                      background: "#f8fafc",
                      borderRadius: 10,
                      fontSize: 14,
                      flexWrap: "wrap",
                      gap: 8,
                    }}
                  >
                    <span style={{ fontWeight: 600 }}>
                      {i + 1}. {pkg.description}
                    </span>
                    <span style={{ color: "#64748b" }}>
                      {pkg.quantity} шт · {Number(pkg.weight_kg)} кг ·{" "}
                      {Number(pkg.width_cm)}×{Number(pkg.height_cm)}×{Number(pkg.depth_cm)} см
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Payment section */}
            <div style={{ ...card, padding: "20px 24px" }}>
              <p style={sectionTitle}>Способ оплаты</p>

              {/* Kaspi Pay placeholder */}
              <div
                style={{
                  border: "2px solid #e5e7eb",
                  borderRadius: 12,
                  padding: "20px 24px",
                  marginBottom: 16,
                  display: "flex",
                  alignItems: "center",
                  gap: 16,
                  cursor: "default",
                }}
              >
                <div
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: 10,
                    background: "#f00",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <span style={{ color: "#fff", fontWeight: 900, fontSize: 18 }}>K</span>
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 15 }}>Kaspi Pay</div>
                  <div style={{ fontSize: 13, color: "#94a3b8", marginTop: 2 }}>
                    Оплата через Kaspi.kz — подключается в следующем этапе
                  </div>
                </div>
              </div>

              {/* Dev note */}
              <div
                style={{
                  padding: "12px 16px",
                  background: "#fefce8",
                  border: "1px solid #fde68a",
                  borderRadius: 10,
                  fontSize: 13,
                  color: "#92400e",
                  marginBottom: 20,
                }}
              >
                <strong>Тестовый режим.</strong> Реальная оплата через Kaspi Pay будет подключена после заключения договора с платёжным шлюзом. Сейчас кнопка симулирует успешную оплату.
              </div>

              {/* Error */}
              {error && (
                <div
                  style={{
                    padding: "12px 16px",
                    background: "#fef2f2",
                    border: "1px solid #fecaca",
                    borderRadius: 10,
                    fontSize: 13,
                    color: "#b91c1c",
                    marginBottom: 16,
                  }}
                >
                  {error}
                </div>
              )}

              {/* Pay button */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
                <div>
                  <div style={{ fontSize: 13, color: "#64748b" }}>Итого к оплате</div>
                  <div style={{ fontSize: 24, fontWeight: 800, color: "#0f172a" }}>
                    {formatPrice(Number(draft.price_snapshot), draft.currency_snapshot)}
                  </div>
                </div>
                <button
                  onClick={() => void handlePay()}
                  disabled={isPaying}
                  style={{
                    background: isPaying ? "#94a3b8" : "#0f172a",
                    color: "#fff",
                    border: "none",
                    borderRadius: 12,
                    padding: "14px 32px",
                    fontSize: 15,
                    fontWeight: 700,
                    cursor: isPaying ? "not-allowed" : "pointer",
                    fontFamily: "inherit",
                    minWidth: 200,
                  }}
                >
                  {isPaying
                    ? "Обрабатываем…"
                    : `Оплатить ${formatPrice(Number(draft.price_snapshot), draft.currency_snapshot)}`}
                </button>
              </div>
            </div>

          </div>
        ) : null}
      </div>
    </main>
  );
}
