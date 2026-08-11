"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { useIsMobile } from "@/hooks/use-is-mobile";
import { ApiError, resendVerificationEmail } from "@/lib/api/auth";
import { listNotifications } from "@/lib/api/notifications";

function IconLogout() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

function BellButton({ unread, onClick }: { unread: number; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      title="Уведомления"
      style={{
        position: "relative",
        width: 36,
        height: 36,
        borderRadius: "50%",
        border: "1px solid #E2E8EE",
        background: "#ffffff",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: unread > 0 ? "#0B2545" : "#94a3b8",
        flexShrink: 0,
      }}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
      {unread > 0 && (
        <span
          style={{
            position: "absolute",
            top: -3,
            right: -3,
            minWidth: 16,
            height: 16,
            borderRadius: 999,
            background: "#ef4444",
            color: "#fff",
            fontSize: 10,
            fontWeight: 700,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "0 4px",
            border: "2px solid #fff",
          }}
        >
          {unread > 9 ? "9+" : unread}
        </span>
      )}
    </button>
  );
}

function VerifyEmailBanner({ email, isMobile }: { email: string; isMobile: boolean }) {
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState<"idle" | "sent" | "error">("idle");
  const [message, setMessage] = useState<string>("");

  async function handleResend() {
    setSending(true);
    setStatus("idle");
    try {
      await resendVerificationEmail();
      setStatus("sent");
      setMessage("Письмо отправлено - проверьте почту.");
    } catch (err) {
      setStatus("error");
      setMessage(
        err instanceof ApiError
          ? err.detail
          : "Не удалось отправить письмо. Попробуйте позже.",
      );
    } finally {
      setSending(false);
    }
  }

  return (
    <div
      style={{
        background: "#FEF3C7",
        borderBottom: "1px solid #FCD34D",
        padding: isMobile ? "12px 16px" : "12px 40px",
        display: "flex",
        alignItems: isMobile ? "flex-start" : "center",
        flexDirection: isMobile ? "column" : "row",
        gap: 10,
        fontFamily: "Inter Variable, sans-serif",
      }}
    >
      <div style={{ flex: 1, fontSize: 13, color: "#78350F", lineHeight: 1.5 }}>
        <b>Подтвердите email.</b> Мы отправили ссылку на <b>{email}</b>. Перейдите по
        ссылке, чтобы оформлять и оплачивать заказы.
        {status !== "idle" && (
          <span style={{ marginLeft: 6, color: status === "sent" ? "#166534" : "#B91C1C", fontWeight: 500 }}>
            {message}
          </span>
        )}
      </div>
      <button
        type="button"
        onClick={handleResend}
        disabled={sending}
        style={{
          padding: "8px 14px",
          borderRadius: 8,
          border: "1px solid #B45309",
          background: sending ? "#FCD34D" : "#FFFFFF",
          color: "#78350F",
          fontSize: 13,
          fontWeight: 600,
          cursor: sending ? "not-allowed" : "pointer",
          fontFamily: "inherit",
          whiteSpace: "nowrap",
          flexShrink: 0,
        }}
      >
        {sending ? "Отправляем…" : "Отправить снова"}
      </button>
    </div>
  );
}

type NavTab = { label: string; href: string; variant: "base" | "admin" | "carrier" };

const BASE_TABS: NavTab[] = [
  { label: "Заказы",          href: "/dashboard/orders",        variant: "base" },
  { label: "Адресная книга",  href: "/dashboard/address-book",  variant: "base" },
  { label: "Уведомления",     href: "/dashboard/notifications", variant: "base" },
  { label: "Профиль",         href: "/dashboard/profile",       variant: "base" },
];

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { logout, currentUser, isAuthenticated } = useAuth();
  const [unreadCount, setUnreadCount] = useState(0);
  const isMobile = useIsMobile();

  useEffect(() => {
    if (!isAuthenticated) return;
    listNotifications()
      .then((res) => setUnreadCount(res.unread_count))
      .catch((err) => console.error("Failed to load notifications:", err));
  }, [isAuthenticated, pathname]);

  const isAdminOrOperator = currentUser?.role === "admin" || currentUser?.role === "operator";
  const isCarrier = currentUser?.role === "carrier";
  const adminTabLabel = currentUser?.role === "operator" ? "Оператор" : "Админ";

  const navTabs: NavTab[] = [
    ...BASE_TABS,
    ...(isAdminOrOperator
      ? [{ label: adminTabLabel, href: "/dashboard/admin", variant: "admin" as const }]
      : []),
    ...(isCarrier
      ? [{ label: "Перевозчик", href: "/dashboard/carrier", variant: "carrier" as const }]
      : []),
  ];

  function handleLogout() {
    logout();
    router.push("/");
  }

  const displayName = currentUser?.full_name || currentUser?.email || "Пользователь";
  const hPad = isMobile ? "0 16px" : "0 40px";

  return (
    <div style={{ minHeight: "100vh", background: "#FAFAFA" }}>

      {/* HEADER */}
      <header
        style={{
          height: 64,
          background: "#ffffff",
          borderBottom: "1px solid #E2E8EE",
          padding: hPad,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          position: "sticky",
          top: 0,
          zIndex: 50,
          gap: 8,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0, overflow: "hidden" }}>
          <Link
            href="/"
            aria-label="Novex — на главную"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              textDecoration: "none",
              font: "700 20px/1 'Space Grotesk Variable', 'Inter Variable', sans-serif",
              letterSpacing: "-0.02em",
              color: "#0E1826",
              flexShrink: 0,
            }}
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
          {!isMobile && (
            <>
              <span style={{ color: "#E2E8EE", fontSize: 18 }}>|</span>
              <span style={{ fontSize: 14, color: "#5F6E7E", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {displayName}
              </span>
            </>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
          <BellButton
            unread={unreadCount}
            onClick={() => router.push("/dashboard/notifications")}
          />
          <button
            onClick={handleLogout}
            style={{
              display: "flex",
              alignItems: "center",
              gap: isMobile ? 0 : 6,
              padding: isMobile ? "8px 10px" : "8px 14px",
              borderRadius: 10,
              border: "1px solid #E2E8EE",
              background: "#ffffff",
              color: "#64748b",
              fontSize: 13,
              fontWeight: 500,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            <IconLogout />
            {!isMobile && "Выйти"}
          </button>
        </div>
      </header>

      {/* NAV TABS - горизонтальный скролл на мобилке */}
      <nav
        style={{
          background: "#ffffff",
          borderBottom: "1px solid #E2E8EE",
          padding: hPad,
          display: "flex",
          gap: 0,
          overflowX: "auto",
          scrollbarWidth: "none",
          WebkitOverflowScrolling: "touch",
        } as React.CSSProperties}
      >
        {navTabs.map(({ label, href, variant }) => {
          const active = pathname.startsWith(href);
          const activeColor =
            variant === "admin" ? "#d97706" :
            variant === "carrier" ? "#4338ca" :
            "#0B2545";
          const activeBorder = activeColor;
          const idleColor =
            variant === "admin" ? "#b45309" :
            variant === "carrier" ? "#4f46e5" :
            "#5F6E7E";
          const showDot = href === "/dashboard/notifications" && unreadCount > 0 && !active;
          return (
            <Link
              key={href}
              href={href}
              style={{
                padding: isMobile ? "12px 14px" : "14px 20px",
                fontSize: isMobile ? 13 : 14,
                fontWeight: active ? 600 : 500,
                textDecoration: "none",
                color: active ? activeColor : idleColor,
                borderBottom: active ? `2px solid ${activeBorder}` : "2px solid transparent",
                marginBottom: -1,
                transition: "color 0.15s",
                whiteSpace: "nowrap",
                display: "flex",
                alignItems: "center",
                gap: 6,
                flexShrink: 0,
              }}
            >
              {label}
              {showDot && (
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#ef4444", display: "inline-block", marginBottom: 1 }} />
              )}
            </Link>
          );
        })}
      </nav>

      {/* VERIFY EMAIL BANNER - visible only until the user confirms their email */}
      {currentUser && currentUser.email_verified === false && (
        <VerifyEmailBanner email={currentUser.email} isMobile={isMobile} />
      )}

      {/* CONTENT */}
      <div
        style={{
          padding: isMobile ? "20px 16px" : "32px 40px",
          background: "#FAFAFA",
          minHeight: "calc(100vh - 128px)",
          fontFamily: "Inter Variable, sans-serif",
        }}
      >
        {children}
      </div>
    </div>
  );
}
