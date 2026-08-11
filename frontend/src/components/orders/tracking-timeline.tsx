// Единый вид «Истории статусов» для клиента, перевозчика и админа.
// Логика по Azimuth (raw description) и защита от дублей «Доставлен/Доставлен»
// живут ЗДЕСЬ — чтобы у всех трёх ролей поведение совпадало и не расходилось.

import { ORDER_STATUS_LABELS } from "@/lib/status-labels";

export interface TrackingEvent {
  status: string;
  description: string | null;
  location: string | null;
  occurred_at: string;
}

// Timeline-цвета (dot/line). Не смешиваем с общим ORDER_STATUS_COLORS —
// там bg/color для badge-пилюль, тут другая семантика.
const TIMELINE_COLORS: Record<string, { dot: string; line: string }> = {
  paid:             { dot: "#16a34a", line: "#bbf7d0" },
  sent_to_carrier:  { dot: "#0B2545", line: "#CFDCEA" },
  picked_up:        { dot: "#0B2545", line: "#CFDCEA" },
  in_transit:       { dot: "#7c3aed", line: "#ddd6fe" },
  out_for_delivery: { dot: "#7c3aed", line: "#ddd6fe" },
  arrived:          { dot: "#7c3aed", line: "#ddd6fe" },
  delivered:        { dot: "#16a34a", line: "#bbf7d0" },
  delivery_failed:  { dot: "#dc2626", line: "#fecaca" },
  returned:         { dot: "#dc2626", line: "#fecaca" },
  cancelled:        { dot: "#dc2626", line: "#fecaca" },
  customs_hold:     { dot: "#d97706", line: "#fde68a" },
};

// Карrier'ы, у которых родное описание информативнее нашего нормализованного
// лейбла — для них показываем сырой текст перевозчика (Azimuth просил).
const RAW_DESCRIPTION_CARRIERS = new Set(["azimuth"]);

function eventLabel(event: TrackingEvent, carrierCode: string | null): string {
  const raw = event.description?.trim();
  if (carrierCode && RAW_DESCRIPTION_CARRIERS.has(carrierCode) && raw) return raw;
  const normalized = ORDER_STATUS_LABELS[event.status];
  if (normalized) return normalized;
  return raw || "Обновление статуса";
}

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export function TrackingTimeline({
  events,
  carrierCode,
}: {
  events: readonly TrackingEvent[];
  carrierCode: string | null;
}) {
  if (events.length === 0) return null;
  return (
    <>
      {events.map((event, idx) => {
        const colors = TIMELINE_COLORS[event.status] ?? { dot: "#94a3b8", line: "#E2E8EE" };
        const isLast = idx === events.length - 1;
        const label = eventLabel(event, carrierCode);
        // subtitle показываем только если description != label — так не
        // получаем дубль вида «Доставлен / Доставлен» (было раньше).
        const subtitle = event.description && event.description.trim() !== label
          ? event.description
          : null;
        return (
          <div key={idx} style={{ display: "flex", gap: 16, paddingBottom: isLast ? 0 : 20 }}>
            {/* dot + line */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
              <div style={{ width: 14, height: 14, borderRadius: "50%", background: colors.dot, boxShadow: `0 0 0 4px ${colors.line}`, flexShrink: 0, marginTop: 3 }} />
              {!isLast && (
                <div style={{ width: 2, flex: 1, background: "#E2E8EE", marginTop: 6, marginBottom: 6, minHeight: 24 }} />
              )}
            </div>
            {/* content */}
            <div style={{ flex: 1, paddingBottom: isLast ? 0 : 4 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#0E1826", marginBottom: 2, lineHeight: 1.3 }}>
                {label}
              </div>
              {subtitle && (
                <div style={{ fontSize: 13, color: "#5F6E7E", marginBottom: 2, lineHeight: 1.4 }}>{subtitle}</div>
              )}
              {event.location && (
                <div style={{ fontSize: 12, color: "#9CA3AF", marginBottom: 2 }}>{event.location}</div>
              )}
              <div style={{ fontSize: 12, color: "#9CA3AF" }}>{formatDateTime(event.occurred_at)}</div>
            </div>
          </div>
        );
      })}
    </>
  );
}
