// Единственный источник правды для статусов заказа и их цветов на всех
// клиентских, админских и карrier-страницах. Подписи на русском и казахском
// живут в messages/{ru,kk}.json → orderStatus.<status> (см. useOrderStatusLabel).
//
// Backend-каноничный список статусов живёт в двух местах:
//   backend/app/common/status_machine.py     - граф переходов
//   backend/app/modules/orders/schemas.py    - OrderDraftStatus Literal
// Держите их синхронно; тут - только UI.
//
// Примечание про Azimuth: в **tracking events** мы показываем сырой текст
// перевозчика (см. RAW_DESCRIPTION_CARRIERS в carrier/orders/[id]/page.tsx и
// dashboard/orders/[id]/tracking/page.tsx). Это НЕ отменяет нормализованные
// подписи для `order.status` - они всё равно приходят из messages.

import { useTranslations } from "next-intl";

export const ORDER_STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  draft:                      { bg: "#f1f5f9", color: "#475569" },
  shipment_details_completed: { bg: "#e0f2fe", color: "#0369a1" },
  ready_for_checkout:         { bg: "#E6EEF7", color: "#0E2E5C" },
  awaiting_payment:           { bg: "#fef3c7", color: "#92400e" },
  payment_under_review:       { bg: "#fef3c7", color: "#92400e" },
  payment_rejected:           { bg: "#fee2e2", color: "#991b1b" },
  paid:                       { bg: "#dcfce7", color: "#166534" },
  dispatch_queued:            { bg: "#e0e7ff", color: "#3730a3" },
  dispatch_failed:            { bg: "#fed7aa", color: "#9a3412" },
  // Оба pending_manual* для клиента означают одно: заказ у нас, ждём
  // перевозчика. Внутренняя разница (auto-dispatch vs manual push) видна
  // только админам через историю статусов.
  pending_manual:             { bg: "#e0e7ff", color: "#3730a3" },
  pending_manual_dispatch:    { bg: "#e0e7ff", color: "#3730a3" },
  sent_to_carrier:            { bg: "#e0f2fe", color: "#0369a1" },
  picked_up:                  { bg: "#c7d2fe", color: "#3730a3" },
  in_transit:                 { bg: "#E6EEF7", color: "#1e40af" },
  out_for_delivery:           { bg: "#ede9fe", color: "#5b21b6" },
  arrived:                    { bg: "#d1fae5", color: "#065f46" },
  delivery_failed:            { bg: "#fed7aa", color: "#9a3412" },
  customs_hold:               { bg: "#fef3c7", color: "#92400e" },
  delivered:                  { bg: "#dcfce7", color: "#166534" },
  return_requested:           { bg: "#fef3c7", color: "#92400e" },
  return_in_progress:         { bg: "#fed7aa", color: "#9a3412" },
  returned:                   { bg: "#f1f5f9", color: "#475569" },
  cancelled:                  { bg: "#fee2e2", color: "#991b1b" },
};

// Все известные статусы в порядке жизненного цикла - удобно для селектов
// в админке. Подпись для каждого должна быть в messages → orderStatus.
export const ORDER_STATUSES: readonly string[] = Object.keys(ORDER_STATUS_COLORS);

// Хелпер: цвета с нейтральным фолбэком.
export function orderStatusColors(status: string): { bg: string; color: string } {
  return ORDER_STATUS_COLORS[status] ?? { bg: "#f1f5f9", color: "#475569" };
}

// Подпись статуса на языке страницы с фолбэком на сырой slug, чтобы никогда
// не ронять UI.
export function useOrderStatusLabel(): (status: string) => string {
  const t = useTranslations("orderStatus");
  return (status: string) => (t.has(status) ? t(status) : status);
}
