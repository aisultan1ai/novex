"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Menu, X } from "lucide-react";
import { useAuth } from "@/components/providers/auth-provider";
import { useIsMobile } from "@/hooks/use-is-mobile";

const NAV_LINKS = [
  { label: "Доставка",      href: "/" },
  { label: "Отслеживание",  href: "/tracking" },
  { label: "Партнёрам",     href: "/partners" },
];

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, isLoading, currentUser } = useAuth();
  const isMobile = useIsMobile();
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Close menu on navigation
  useEffect(() => { setMenuOpen(false); }, [pathname]);

  // Lock scroll when menu open
  useEffect(() => {
    document.body.style.overflow = menuOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [menuOpen]);

  return (
    <>
      <header
        style={{
          position: "sticky",
          top: 0,
          zIndex: 50,
          height: 64,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: isMobile ? "0 20px" : "0 48px",
          background: menuOpen ? "#ffffff" : scrolled ? "rgba(255,255,255,0.85)" : "#ffffff",
          backdropFilter: scrolled && !menuOpen ? "blur(8px)" : "none",
          WebkitBackdropFilter: scrolled && !menuOpen ? "blur(8px)" : "none",
          borderBottom: "1px solid #E2E8EE",
          transition: "background 0.2s, box-shadow 0.2s",
          boxShadow: scrolled && !menuOpen ? "0 1px 8px rgba(0,0,0,0.06)" : "none",
        }}
      >
        {/* Logo */}
        <Link
          href="/"
          onClick={(e) => {
            if (pathname === "/") {
              e.preventDefault();
              window.dispatchEvent(new CustomEvent("novex:resetHome"));
              window.scrollTo({ top: 0, behavior: "smooth" });
            } else {
              router.push("/");
            }
          }}
          aria-label="Novex — на главную"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            textDecoration: "none",
            font: "700 22px/1 'Space Grotesk Variable', 'Inter Variable', sans-serif",
            letterSpacing: "-0.02em",
            color: "#0B2545",
          }}
        >
          <svg
            width="30"
            height="27"
            viewBox="10 11 38 34"
            fill="none"
            role="img"
            aria-hidden="true"
            style={{ flexShrink: 0, display: "block" }}
          >
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

        {/* Desktop nav links */}
        {!isMobile && (
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
                    color: active ? "#0E1826" : "#5F6E7E",
                    textDecoration: "none",
                    display: "flex",
                    alignItems: "center",
                    borderBottom: active ? "2px solid #22C9E0" : "2px solid transparent",
                    transition: "color 0.15s, border-color 0.15s",
                  }}
                  onMouseEnter={(e) => { if (!active) e.currentTarget.style.color = "#0E1826"; }}
                  onMouseLeave={(e) => { if (!active) e.currentTarget.style.color = "#5F6E7E"; }}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        )}

        {/* Desktop auth buttons */}
        {!isMobile && !isLoading && (
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            {isAuthenticated ? (
              <Link
                href="/dashboard"
                style={{
                  font: "600 15px/1 Inter Variable, sans-serif",
                  color: "#ffffff",
                  background: "#0B2545",
                  padding: "10px 18px",
                  borderRadius: 10,
                  textDecoration: "none",
                  transition: "background 0.15s",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "#0E2E5C")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "#0B2545")}
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
                    color: "#0E1826",
                    textDecoration: "none",
                    transition: "color 0.15s",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = "#0B2545")}
                  onMouseLeave={(e) => (e.currentTarget.style.color = "#0E1826")}
                >
                  Войти
                </Link>
                <Link
                  href="/register"
                  style={{
                    font: "600 15px/1 Inter Variable, sans-serif",
                    color: "#ffffff",
                    background: "#0B2545",
                    padding: "10px 18px",
                    borderRadius: 10,
                    textDecoration: "none",
                    transition: "background 0.15s",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "#0E2E5C")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "#0B2545")}
                >
                  Регистрация
                </Link>
              </>
            )}
          </div>
        )}

        {/* Mobile burger button */}
        {isMobile && (
          <button
            onClick={() => setMenuOpen((o) => !o)}
            aria-label={menuOpen ? "Закрыть меню" : "Открыть меню"}
            aria-expanded={menuOpen}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: 8,
              margin: -8,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#0E1826",
              borderRadius: 8,
            }}
          >
            {menuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        )}
      </header>

      {/* Mobile menu overlay */}
      {isMobile && menuOpen && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: "fixed",
            top: 64,
            left: 0,
            right: 0,
            bottom: 0,
            background: "#ffffff",
            zIndex: 49,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            borderTop: "1px solid #E2E8EE",
          }}
        >
          {/* Nav links */}
          <nav style={{ display: "flex", flexDirection: "column" }}>
            {NAV_LINKS.map(({ label, href }) => {
              const active =
                href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    padding: "17px 20px",
                    font: "500 17px/1 Inter Variable, sans-serif",
                    color: active ? "#0B2545" : "#0E1826",
                    textDecoration: "none",
                    borderBottom: `1px solid ${active ? "#22C9E0" : "#F1F5F9"}`,
                    background: active ? "#F1F5F9" : "transparent",
                  }}
                >
                  {label}
                </Link>
              );
            })}
          </nav>

          {/* Auth buttons */}
          {!isLoading && (
            <div style={{ padding: "24px 20px", display: "flex", flexDirection: "column", gap: 12 }}>
              {isAuthenticated ? (
                <Link
                  href="/dashboard"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    height: 52,
                    borderRadius: 10,
                    background: "#0B2545",
                    color: "#ffffff",
                    font: "600 16px/1 Inter Variable, sans-serif",
                    textDecoration: "none",
                  }}
                >
                  {currentUser?.full_name
                    ? `${currentUser.full_name.split(" ")[0]} · Кабинет`
                    : "Личный кабинет"}
                </Link>
              ) : (
                <>
                  <Link
                    href="/register"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      height: 52,
                      borderRadius: 10,
                      background: "#0B2545",
                      color: "#ffffff",
                      font: "600 16px/1 Inter Variable, sans-serif",
                      textDecoration: "none",
                    }}
                  >
                    Зарегистрироваться
                  </Link>
                  <Link
                    href="/login"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      height: 52,
                      borderRadius: 10,
                      background: "#ffffff",
                      border: "1.5px solid #E2E8EE",
                      color: "#0E1826",
                      font: "600 16px/1 Inter Variable, sans-serif",
                      textDecoration: "none",
                    }}
                  >
                    Войти
                  </Link>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </>
  );
}
