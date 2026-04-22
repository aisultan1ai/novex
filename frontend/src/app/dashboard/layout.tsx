"use client";

import type { CSSProperties, ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";

const sidebarStyle: CSSProperties = {
  width: 220,
  minHeight: "100vh",
  background: "#0f172a",
  color: "#cbd5e1",
  display: "flex",
  flexDirection: "column",
  padding: "32px 0",
  flexShrink: 0,
};

const logoStyle: CSSProperties = {
  padding: "0 24px 32px",
  fontSize: 20,
  fontWeight: 800,
  color: "#ffffff",
  letterSpacing: "-0.5px",
  borderBottom: "1px solid #1e293b",
};

const navStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 4,
  padding: "24px 12px",
  flex: 1,
};

const mainStyle: CSSProperties = {
  flex: 1,
  minHeight: "100vh",
  background: "linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%)",
  fontFamily:
    "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
};

const contentStyle: CSSProperties = {
  maxWidth: 1000,
  margin: "0 auto",
  padding: "40px 24px 80px",
};

function NavLink({
  href,
  label,
  active,
}: {
  href: string;
  label: string;
  active: boolean;
}) {
  const linkStyle: CSSProperties = {
    display: "block",
    padding: "10px 12px",
    borderRadius: 10,
    fontSize: 14,
    fontWeight: active ? 600 : 400,
    color: active ? "#ffffff" : "#94a3b8",
    background: active ? "#1e293b" : "transparent",
    textDecoration: "none",
    transition: "background 0.15s",
  };

  return (
    <Link href={href} style={linkStyle}>
      {label}
    </Link>
  );
}

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { logout } = useAuth();

  function handleLogout() {
    logout();
    router.push("/");
  }

  return (
    <div style={{ display: "flex" }}>
      <aside style={sidebarStyle}>
        <div style={logoStyle}>Novex</div>

        <nav style={navStyle}>
          <NavLink
            href="/dashboard/orders"
            label="Мои заказы"
            active={pathname.startsWith("/dashboard/orders")}
          />
          <NavLink
            href="/dashboard/profile"
            label="Профиль"
            active={pathname === "/dashboard/profile"}
          />
          <NavLink
            href="/"
            label="Новая доставка"
            active={false}
          />
        </nav>

        <div style={{ padding: "0 12px" }}>
          <button
            onClick={handleLogout}
            style={{
              width: "100%",
              padding: "10px 12px",
              borderRadius: 10,
              background: "transparent",
              border: "1px solid #334155",
              color: "#94a3b8",
              fontSize: 14,
              cursor: "pointer",
              textAlign: "left",
            }}
          >
            Выйти
          </button>
        </div>
      </aside>

      <main style={mainStyle}>
        <div style={contentStyle}>{children}</div>
      </main>
    </div>
  );
}
