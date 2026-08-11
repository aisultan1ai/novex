"use client";

import Link from "next/link";
import { useIsMobile } from "@/hooks/use-is-mobile";
import { CONTACTS, phoneHref } from "@/lib/config/contacts";

const FOOTER_COLS = [
  {
    title: "Сервис",
    links: [
      { label: "Рассчитать доставку", href: "/" },
      { label: "Отслеживание", href: "/tracking" },
      { label: "Партнёрам", href: "/partners" },
    ],
  },
  {
    title: "Поддержка",
    links: [
      { label: "Часто задаваемые вопросы", href: "/#help" },
      { label: "Написать в поддержку", href: `mailto:${CONTACTS.supportEmail}` },
      { label: "Условия доставки", href: "/terms" },
    ],
  },
  {
    title: "Контакты",
    links: [
      { label: CONTACTS.supportEmail, href: `mailto:${CONTACTS.supportEmail}` },
      { label: CONTACTS.supportPhone, href: phoneHref(CONTACTS.supportPhone) },
      { label: CONTACTS.officeAddress, href: "#" },
    ],
  },
];

export default function Footer() {
  const isMobile = useIsMobile();

  return (
    <footer
      style={{
        background: "#0B2545",
        color: "#94A3B8",
        padding: isMobile ? "40px 20px 24px" : "64px 48px 32px",
      }}
    >
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        {/* Top row */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: isMobile ? "1fr 1fr" : "1.5fr 1fr 1fr 1fr",
            gap: isMobile ? 32 : 48,
            marginBottom: isMobile ? 36 : 48,
          }}
        >
          {/* Brand - spans both columns on mobile */}
          <div style={isMobile ? { gridColumn: "1 / -1" } : {}}>
            <Link
              href="/"
              aria-label="Novex — на главную"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 10,
                textDecoration: "none",
                font: "700 22px/1 'Space Grotesk Variable', 'Inter Variable', sans-serif",
                letterSpacing: "-0.02em",
                color: "#ffffff",
                marginBottom: 16,
              }}
            >
              <svg
                width="34"
                height="30"
                viewBox="10 11 38 34"
                fill="none"
                role="img"
                aria-hidden="true"
                style={{ flexShrink: 0, display: "block" }}
              >
                <circle cx="17" cy="28" r="5" fill="#22C9E0" />
                <line x1="20" y1="25.5" x2="37" y2="17" stroke="#94A3B8" strokeWidth="2.2" strokeLinecap="round" />
                <line x1="21" y1="28" x2="38" y2="28" stroke="#22C9E0" strokeWidth="2.4" strokeLinecap="round" />
                <line x1="20" y1="30.5" x2="37" y2="39" stroke="#94A3B8" strokeWidth="2.2" strokeLinecap="round" />
                <circle cx="40" cy="16" r="3.4" fill="#94A3B8" />
                <circle cx="41" cy="28" r="4.6" fill="#22C9E0" />
                <circle cx="40" cy="40" r="3.4" fill="#94A3B8" />
              </svg>
              <span>n<span style={{ color: "#22C9E0" }}>o</span>vex</span>
            </Link>
            <p
              style={{
                font: "400 15px/1.6 Inter Variable, sans-serif",
                color: "#64748B",
                margin: "12px 0 0",
                maxWidth: 260,
              }}
            >
              Агрегатор курьерских служб Казахстана. Сравниваем тарифы и
              оформляем доставку в пару кликов.
            </p>
          </div>

          {/* Link columns */}
          {FOOTER_COLS.map((col) => (
            <div key={col.title}>
              <div
                style={{
                  font: "600 13px/1 Inter Variable, sans-serif",
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  color: "#ffffff",
                  marginBottom: 20,
                }}
              >
                {col.title}
              </div>
              <ul
                style={{
                  listStyle: "none",
                  margin: 0,
                  padding: 0,
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                {col.links.map((l) => (
                  <li key={l.label}>
                    <Link
                      href={l.href}
                      style={{
                        font: "400 14px/1.4 Inter Variable, sans-serif",
                        color: "#94A3B8",
                        textDecoration: "none",
                        transition: "color 0.15s",
                      }}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.color = "#ffffff")
                      }
                      onMouseLeave={(e) =>
                        (e.currentTarget.style.color = "#94A3B8")
                      }
                    >
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Divider */}
        <div style={{ height: 1, background: "#163558", margin: "0 0 24px" }} />

        {/* Bottom row */}
        <div
          style={{
            display: "flex",
            flexDirection: isMobile ? "column" : "row",
            justifyContent: "space-between",
            alignItems: isMobile ? "flex-start" : "center",
            gap: 12,
          }}
        >
          <span
            style={{
              font: "400 13px/1 Inter Variable, sans-serif",
              color: "#64748B",
            }}
          >
            © {new Date().getFullYear()} Novex. Все права защищены.
          </span>
          <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
            {[
              { label: "Политика конфиденциальности", href: "/privacy" },
              { label: "Условия использования", href: "/terms" },
            ].map((l) => (
              <Link
                key={l.href}
                href={l.href}
                style={{
                  font: "400 13px/1 Inter Variable, sans-serif",
                  color: "#64748B",
                  textDecoration: "none",
                  transition: "color 0.15s",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "#94A3B8")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "#64748B")}
              >
                {l.label}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
