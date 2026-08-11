// Единственный источник правды для подписей/цветов статусов заказа
// на всех клиентских, админских и карrier-страницах.
//
// Backend-каноничный список статусов живёт в двух местах:
//   backend/app/common/status_machine.py     - граф переходов
//   backend/app/modules/orders/schemas.py    - OrderDraftStatus Literal
// Держите их синхронно; тут - только UI-метки.
//
// Примечание про Azimuth: в **tracking events** мы показываем сырой текст
// перевозчика (см. RAW_DESCRIPTION_CARRIERS в carrier/orders/[id]/page.tsx и
// dashboard/orders/[id]/tracking/page.tsx). Это НЕ отменяет нормализованные
// подписи для `order.status` - они всё равно приходят из этого файла.

export const ORDER_STATUS_LABELS: Record<string, string> = {
  draft:                      "Черновик",
  shipment_details_completed: "Детали заполнены",
  ready_for_checkout:         "Готов к оплате",
  awaiting_payment:           "Ожидает оплаты",
  payment_under_review:       "Чек на проверке",
  payment_rejected:           "Чек отклонён",
  paid:                       "Оплачен",
  dispatch_queued:            "Ожидает отправки",
  dispatch_failed:            "Уточняем детали",
  // Оба pending_manual* для клиента означают одно: заказ у нас, ждём
  // перевозчика. Внутренняя разница (auto-dispatch vs manual push) видна
  // только админам через историю статусов.
  pending_manual:             "Передаётся перевозчику",
  pending_manual_dispatch:    "Передаётся перевозчику",
  sent_to_carrier:            "Передан перевозчику",
  picked_up:                  "Забран",
  in_transit:                 "В пути",
  out_for_delivery:           "Выезд на доставку",
  arrived:                    "Прибыл в пункт выдачи",
  delivery_failed:            "Попытка доставки не удалась",
  customs_hold:               "Задержан на таможне",
  delivered:                  "Доставлен",
  return_requested:           "Запрос возврата",
  return_in_progress:         "Возврат в пути",
  returned:                   "Возвращён",
  cancelled:                  "Отменён",
};

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
// в админке и для проверки, что подписи покрывают весь Literal.
export const ORDER_STATUSES: readonly string[] = Object.keys(ORDER_STATUS_LABELS);

// Хелпер: подпись с фолбэком на сырой slug, чтобы никогда не ронять UI.
export function orderStatusLabel(status: string): string {
  return ORDER_STATUS_LABELS[status] ?? status;
}

// Хелпер: цвета с нейтральным фолбэком.
export function orderStatusColors(status: string): { bg: string; color: string } {
  return ORDER_STATUS_COLORS[status] ?? { bg: "#f1f5f9", color: "#475569" };
}
