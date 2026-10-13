"use client";

import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { errorMessage, responseToApiError, safeFetch } from "@/lib/api/client";

type Props = {
  /** API-путь БЕЗ префикса /api/v1 (например "/admin/orders/export"). */
  endpoint: string;
  /** Query-строка фильтров (например "status=paid&date_from=..."). */
  query?: string;
  /** Подпись кнопки. По умолчанию «Экспорт .xlsx». */
  label?: string;
  /** Стиль контура (по умолчанию outline navy). */
  variant?: "outline" | "solid";
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") ?? "/api/v1";

/**
 * Кнопка экспорта в XLSX. Делает `fetch` с credentials (httpOnly-cookie),
 * при 2xx скачивает blob, при ошибке показывает alert с сообщением с бэка.
 * Плюс: не покидаем страницу (в отличие от `window.open`), можно поймать
 * 422 "нет данных / слишком много" и показать нормальный текст.
 */
export default function ExportXlsxButton({
  endpoint,
  query,
  label,
  variant = "outline",
}: Props) {
  const t = useTranslations("export");
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    if (busy) return;
    setBusy(true);
    try {
      const url = `${API_BASE}${endpoint}${query ? `?${query}` : ""}`;
      const res = await safeFetch(url, { credentials: "include", cache: "no-store" });

      if (!res.ok) {
        alert((await responseToApiError(res)).detail);
        return;
      }

      // Content-Disposition: attachment; filename="..."  → достаём имя файла
      const cd = res.headers.get("Content-Disposition") ?? "";
      const match = cd.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
      const filename = match ? decodeURIComponent(match[1]) : "export.xlsx";

      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      // Пауза перед revoke — Firefox иногда не успевает начать download до revoke.
      setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch (e) {
      alert(errorMessage(e, t("failed")));
    } finally {
      setBusy(false);
    }
  }

  const isSolid = variant === "solid";
  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      aria-busy={busy}
      aria-live="polite"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "10px 14px",
        borderRadius: 10,
        border: `1.5px solid ${isSolid ? "#0B2545" : "#E2E8EE"}`,
        background: isSolid ? "#0B2545" : "#ffffff",
        color: isSolid ? "#ffffff" : "#0B2545",
        fontSize: 14,
        fontWeight: 600,
        fontFamily: "inherit",
        cursor: busy ? "wait" : "pointer",
        opacity: busy ? 0.7 : 1,
        transition: "background 0.15s, border-color 0.15s",
      }}
      title={busy ? t("busyTitle") : t("title")}
    >
      {busy ? (
        <Loader2 size={16} style={{ animation: "spin 0.8s linear infinite" }} aria-hidden />
      ) : (
        <Download size={16} aria-hidden />
      )}
      {busy ? t("busy") : (label ?? t("label"))}
    </button>
  );
}
