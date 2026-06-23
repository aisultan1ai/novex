"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/providers/auth-provider";

const NAV_LINKS = [
  { label: "Доставка",      href: "/" },
  { label: "Отслеживание",  href: "/tracking" },
  { label: "Помощь",        href: "/#help" },
];

export default function Navbar() {
  const pathname = usePathname();
  const { isAuthenticated, isLoading, currentUser } = useAuth();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        height: 64,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 48px",
        background: scrolled ? "rgba(255,255,255,0.85)" : "#ffffff",
        backdropFilter: scrolled ? "blur(8px)" : "none",
        WebkitBackdropFilter: scrolled ? "blur(8px)" : "none",
        borderBottom: "1px solid #E5E7EB",
        transition: "background 0.2s, box-shadow 0.2s",
        boxShadow: scrolled ? "0 1px 8px rgba(0,0,0,0.06)" : "none",
      }}
    >
      {/* Logo */}
      <Link
        href="/"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 9,
          textDecoration: "none",
          font: "700 22px/1 Inter Variable, sans-serif",
          letterSpacing: "-0.02em",
          color: "#111827",
        }}
      >
        <span
          style={{
            width: 11,
            height: 11,
            borderRadius: "50%",
            background: "#2563EB",
            flexShrink: 0,
          }}
        />
        novex
      </Link>

      {/* Nav links */}
      <nav style={{ display: "flex", gap: 30, height: 64, alignItems: "stretch" }}>
        {NAV_LINKS.map(({ label, href }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              style={{
                font: "500 15px/1 Inter Variable, sans-serif",
                color: active ? "#111827" : "#6B7280",
                textDecoration: "none",
                display: "flex",
                alignItems: "center",
                borderBottom: active ? "2px solid #2563EB" : "2px solid transparent",
                transition: "color 0.15s, border-color 0.15s",
              }}
              onMouseEnter={(e) => { if (!active) e.currentTarget.style.color = "#111827"; }}
              onMouseLeave={(e) => { if (!active) e.currentTarget.style.color = "#6B7280"; }}
            >
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Auth buttons */}
      {!isLoading && (
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          {isAuthenticated ? (
            <Link
              href="/dashboard"
              style={{
                font: "600 15px/1 Inter Variable, sans-serif",
                color: "#ffffff",
                background: "#2563EB",
                padding: "10px 18px",
                borderRadius: 10,
                textDecoration: "none",
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "#1D4ED8")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "#2563EB")
              }
            >
              {currentUser?.full_name
                ? currentUser.full_name.split(" ")[0]
                : "Кабинет"}
            </Link>
          ) : (
            <>
              <Link
                href="/login"
                style={{
                  font: "600 15px/1 Inter Variable, sans-serif",
                  color: "#111827",
                  textDecoration: "none",
                  transition: "color 0.15s",
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.color = "#2563EB")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.color = "#111827")
                }
              >
                Войти
              </Link>
              <Link
                href="/register"
                style={{
                  font: "600 15px/1 Inter Variable, sans-serif",
                  color: "#ffffff",
                  background: "#2563EB",
                  padding: "10px 18px",
                  borderRadius: 10,
                  textDecoration: "none",
                  transition: "background 0.15s",
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = "#1D4ED8")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "#2563EB")
                }
              >
                Регистрация
              </Link>
            </>
          )}
        </div>
      )}
    </header>
  );
}
