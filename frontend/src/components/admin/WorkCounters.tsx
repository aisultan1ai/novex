"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getWorkCounters, type WorkCounters as Counters } from "@/lib/api/admin";
import { useIsMobile } from "@/hooks/use-is-mobile";

interface RowDef {
  key: keyof Counters;
  label: string;
  hint: string;
  href: string;
  // Rare problems: the row is hidden while the count is zero.
  hideWhenZero?: boolean;
}

// Order matters: the most frequent operator task first.
const ROWS: RowDef[] = [
  { key: "payment_review",       label: "Ждут проверки оплаты",   hint: "Клиент загрузил чек",          href: "/dashboard/admin/orders?status=payment_under_review" },
  { key: "awaiting_dispatch",    label: "Ждут отправки",          hint: "Оплачены, уходят перевозчику", href: "/dashboard/admin/orders?status=paid,dispatch_queued" },
  { key: "cancellation_pending", label: "Заявки на отмену",       hint: "Нужно решение",                href: "/dashboard/admin/cancellations" },
  { key: "dispatch_failed",      label: "Ошибки отправки",        hint: "Не ушли перевозчику",          href: "/dashboard/admin/orders?status=dispatch_failed" },
  { key: "orphan_waybills",      label: "Неотменённые накладные", hint: "После переноса забора",        href: "/dashboard/admin/orders?orphan=1",  hideWhenZero: true },
  { key: "stuck_dispatch_jobs",  label: "Зависшие отправки",      hint: "Не завершились за 10 минут",   href: "/dashboard/admin/dispatch-queue",   hideWhenZero: true },
];

const NAVY = "#0B2545";
const MUTED = "#94a3b8";
const BORDER = "#E2E8EE";

/** «Требует внимания» — things that need a human (audit T6). */
export default function WorkCounters() {
  const isMobile = useIsMobile();
  const [counters, setCounters] = useState<Counters | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      getWorkCounters()
        .then((c) => { if (alive) { setCounters(c); setError(null); } })
        .catch((e: Error) => { if (alive) setError(e.message); });
    void load();
    // Keep the desk fresh while it is open — a new proof shows up without a reload.
    const t = setInterval(load, 60_000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const rows = ROWS.filter((r) => !r.hideWhenZero || (counters?.[r.key] ?? 0) > 0);
  const columns = isMobile ? 1 : 2;

  return (
    <section style={{ marginBottom: 32 }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 10 }}>
        Требует внимания
      </div>

      {error && (
        <div style={{ fontSize: 13, color: "#64748b", marginBottom: 10 }}>Не удалось загрузить счётчики: {error}</div>
      )}

      <div
        style={{
          background: "#ffffff",
          border: `1px solid ${BORDER}`,
          borderRadius: 16,
          overflow: "hidden",
          display: "grid",
          gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
        }}
      >
        {rows.map((r, i) => {
          const value = counters?.[r.key];
          const active = (value ?? 0) > 0;
          const lastRow = i >= rows.length - (rows.length % columns || columns);
          return (
            <Link
              key={r.key}
              href={r.href}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: isMobile ? "14px 16px" : "16px 20px",
                textDecoration: "none",
                borderBottom: lastRow ? "none" : `1px solid ${BORDER}`,
                borderRight: columns > 1 && i % columns === 0 ? `1px solid ${BORDER}` : "none",
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "#F8FAFC"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: active ? NAVY : "#64748b" }}>{r.label}</div>
                <div style={{ fontSize: 12, color: MUTED, marginTop: 2 }}>{r.hint}</div>
              </div>
              <div style={{ fontSize: 22, fontWeight: 700, color: active ? NAVY : "#CBD5E1", minWidth: 24, textAlign: "right" }}>
                {value ?? "–"}
              </div>
              <span aria-hidden style={{ color: "#CBD5E1", fontSize: 18, lineHeight: 1 }}>›</span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
