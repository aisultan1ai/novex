"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    if (typeof window !== "undefined") {
      console.error("App error boundary caught:", error);
    }
  }, [error]);

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: 24,
      background: "#FAFAFA",
      fontFamily: "Inter Variable, sans-serif",
    }}>
      <div style={{
        maxWidth: 480,
        width: "100%",
        background: "#FFFFFF",
        border: "1px solid #E5E7EB",
        borderRadius: 16,
        padding: "32px 32px 28px",
        boxShadow: "0 4px 12px rgba(15,23,42,0.06)",
      }}>
        <div style={{
          width: 48, height: 48, borderRadius: "50%",
          background: "#FEE2E2",
          display: "flex", alignItems: "center", justifyContent: "center",
          marginBottom: 16,
        }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#DC2626" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <h1 style={{
          margin: "0 0 8px",
          fontSize: 20, fontWeight: 700,
          color: "#111827",
        }}>
          Что-то пошло не так
        </h1>
        <p style={{
          margin: "0 0 24px",
          fontSize: 14, lineHeight: 1.55,
          color: "#6B7280",
        }}>
          Произошла непредвиденная ошибка на странице. Попробуйте обновить или вернуться на главную.
          Если ошибка повторяется, напишите в поддержку.
        </p>
        {error.digest && (
          <p style={{
            margin: "0 0 20px",
            padding: "8px 12px",
            background: "#F9FAFB",
            border: "1px solid #E5E7EB",
            borderRadius: 8,
            fontSize: 11,
            fontFamily: "monospace",
            color: "#6B7280",
            wordBreak: "break-all",
          }}>
            ID: {error.digest}
          </p>
        )}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button
            onClick={reset}
            style={{
              padding: "10px 20px", borderRadius: 10,
              border: "none", background: "#2563EB", color: "#FFFFFF",
              fontSize: 14, fontWeight: 600, cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Попробовать снова
          </button>
          <Link
            href="/"
            style={{
              padding: "10px 20px", borderRadius: 10,
              border: "1px solid #E5E7EB", background: "#FFFFFF", color: "#374151",
              fontSize: 14, fontWeight: 600, textDecoration: "none",
              display: "inline-flex", alignItems: "center",
            }}
          >
            На главную
          </Link>
        </div>
      </div>
    </div>
  );
}
