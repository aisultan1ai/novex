"use client";

import { useTranslations } from "next-intl";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Link, useRouter } from "@/i18n/navigation";

/**
 * Legacy compatibility redirect. Old links used `?orderId=…`; the current
 * checkout screen lives at `/checkout?draftId=…`. Historically this page
 * silently `router.replace()`-d and, on a bad link, dumped the user on
 * `/dashboard/orders` with no explanation - leaving them wondering why the
 * "pay now" email/notification led nowhere. Now we always render a brief
 * status card so the redirect is visible, and provide a manual escape hatch
 * if the auto-navigation is blocked (e.g. by a stricter browser policy).
 */
function PaymentRedirect() {
  const t = useTranslations("checkout.redirect");
  const router = useRouter();
  const searchParams = useSearchParams();
  const rawOrderId = searchParams.get("orderId");
  const parsed = rawOrderId ? Number(rawOrderId) : NaN;
  const draftId = Number.isInteger(parsed) && parsed > 0 ? parsed : null;

  // We split target vs message so a "no id" case can still render the same UI
  // shape (spinner + "opening") rather than switching to a blank screen.
  const target = draftId ? `/checkout?draftId=${draftId}` : "/dashboard/orders";
  const [redirected, setRedirected] = useState(false);

  useEffect(() => {
    // Short delay so the "Открываем оплату…" card is visible for a beat -
    // the user gets confirmation that something is happening before the URL
    // changes underneath them.
    const t = setTimeout(() => {
      router.replace(target);
      setRedirected(true);
    }, 400);
    return () => clearTimeout(t);
  }, [router, target]);

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex", alignItems: "center", justifyContent: "center",
      background: "#FAFAFA", padding: 20,
    }}>
      <div style={{
        background: "#fff",
        border: "1px solid #E2E8EE",
        borderRadius: 16,
        padding: "28px 32px",
        maxWidth: 440, width: "100%",
        textAlign: "center",
        boxShadow: "0 2px 8px rgba(17,24,39,0.04)",
      }}>
        <div style={{
          fontSize: 32, marginBottom: 12, lineHeight: 1,
        }}>{draftId ? "💳" : "📦"}</div>

        <h1 style={{
          margin: "0 0 8px",
          font: "700 18px/1.3 Inter Variable, sans-serif",
          color: "#0E1826",
        }}>
          {draftId
            ? (redirected ? t("opening") : t("preparing"))
            : t("expired")}
        </h1>

        <p style={{
          margin: "0 0 20px",
          font: "400 14px/1.55 Inter Variable, sans-serif",
          color: "#5F6E7E",
        }}>
          {draftId
            ? t("hint")
            : t("noOrder")}
        </p>

        <Link
          href={target}
          style={{
            display: "inline-block",
            background: "#0B2545",
            color: "#fff",
            padding: "12px 24px",
            borderRadius: 10,
            font: "600 14px/1 Inter Variable, sans-serif",
            textDecoration: "none",
          }}
        >
          {draftId ? t("go") : t("orders")}
        </Link>
      </div>
    </div>
  );
}

export default function PaymentPage() {
  return <Suspense><PaymentRedirect /></Suspense>;
}
