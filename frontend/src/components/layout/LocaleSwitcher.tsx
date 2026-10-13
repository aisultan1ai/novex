"use client";

import { useEffect, useId, useRef, useState, useTransition } from "react";
import { Check, ChevronDown, Globe } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { useAuth } from "@/components/providers/auth-provider";
import { usePathname, useRouter } from "@/i18n/navigation";
import { routing, type Locale } from "@/i18n/routing";
import { saveMyLocale } from "@/lib/api/auth";

// Короткий код на кнопке. В адресе казахская версия тоже /kz.
const CODE: Record<Locale, string> = { ru: "RU", kk: "KZ" };

/**
 * Переключатель языка: глобус + код текущего языка, по клику — меню с полными
 * названиями («Русский», «Қазақша»). Ведёт на тот же путь в другой локали
 * (/tracking ↔ /kz/tracking) с сохранением query-строки.
 *
 * tone="dark" — для navy-фона (футер); placement="top" — меню открывается вверх;
 * align — к какому краю кнопки прижато меню (слева у кнопки у края экрана).
 */
export default function LocaleSwitcher({
  tone = "light",
  placement = "bottom",
  align = "right",
}: {
  tone?: "light" | "dark";
  placement?: "bottom" | "top";
  align?: "left" | "right";
}) {
  const locale = useLocale() as Locale;
  const t = useTranslations("localeSwitcher");
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const [isPending, startTransition] = useTransition();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const menuId = useId();

  // Закрытие по клику вне меню и по Escape (фокус возвращается на кнопку).
  useEffect(() => {
    if (!open) return;
    function onPointer(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // При открытии — фокус на текущий язык, чтобы с клавиатуры было удобно.
  useEffect(() => {
    if (open) itemRefs.current[routing.locales.indexOf(locale)]?.focus();
  }, [open, locale]);

  function switchTo(next: Locale) {
    setOpen(false);
    if (next === locale) return;
    // Query читаем в момент клика, а не через useSearchParams: тот требует
    // Suspense-границу на каждой статически генерируемой странице.
    const href = `${pathname}${window.location.search}`;
    startTransition(() => router.replace(href, { locale: next, scroll: false }));
    // Вошедшему пользователю запоминаем язык в профиле: на нём придут письма
    // и уведомления. Ошибка не мешает переключению.
    if (isAuthenticated) void saveMyLocale(next).catch(() => {});
  }

  function onMenuKey(e: React.KeyboardEvent) {
    const items = itemRefs.current.filter(Boolean) as HTMLButtonElement[];
    const i = items.indexOf(document.activeElement as HTMLButtonElement);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const step = e.key === "ArrowDown" ? 1 : -1;
      items[(i + step + items.length) % items.length]?.focus();
    } else if (e.key === "Tab") {
      setOpen(false);
    }
  }

  const dark = tone === "dark";
  return (
    <div ref={rootRef} style={{ position: "relative", display: "inline-flex" }}>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={`${t("label")}: ${t(locale)}`}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          height: 36,
          padding: "0 10px",
          borderRadius: 9,
          border: `1px solid ${dark ? "rgba(255,255,255,0.16)" : open ? "#0B2545" : "#E2E8EE"}`,
          background: dark ? "transparent" : "#ffffff",
          color: dark ? "#E2E8EE" : "#0B2545",
          font: "600 13px/1 Inter Variable, sans-serif",
          letterSpacing: "0.02em",
          cursor: "pointer",
          opacity: isPending ? 0.6 : 1,
          transition: "border-color 0.15s, opacity 0.15s",
        }}
      >
        <Globe size={16} aria-hidden />
        <span>{CODE[locale]}</span>
        <ChevronDown
          size={14}
          aria-hidden
          style={{ transition: "transform 0.15s", transform: open ? "rotate(180deg)" : "none" }}
        />
      </button>

      {open && (
        <div
          id={menuId}
          role="menu"
          aria-label={t("label")}
          onKeyDown={onMenuKey}
          style={{
            position: "absolute",
            ...(align === "left" ? { left: 0 } : { right: 0 }),
            ...(placement === "top" ? { bottom: "calc(100% + 6px)" } : { top: "calc(100% + 6px)" }),
            minWidth: 168,
            padding: 4,
            background: "#ffffff",
            border: "1px solid #E2E8EE",
            borderRadius: 10,
            boxShadow: "0 8px 24px rgba(11,37,69,0.12)",
            zIndex: 60,
          }}
        >
          {routing.locales.map((l, i) => {
            const active = l === locale;
            return (
              <button
                key={l}
                ref={(el) => { itemRefs.current[i] = el; }}
                type="button"
                role="menuitemradio"
                aria-checked={active}
                lang={l}
                onClick={() => switchTo(l)}
                onMouseEnter={(e) => (e.currentTarget.style.background = "#F1F5F9")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 12,
                  padding: "9px 10px",
                  border: "none",
                  borderRadius: 7,
                  background: "transparent",
                  color: "#0E1826",
                  font: `${active ? 600 : 500} 14px/1 Inter Variable, sans-serif`,
                  textAlign: "left",
                  cursor: "pointer",
                }}
              >
                <span>{t(l)}</span>
                {active && <Check size={16} color="#22C9E0" aria-hidden />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
