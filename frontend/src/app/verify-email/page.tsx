"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { ApiError, verifyEmail } from "@/lib/api/auth";

type PageState = "loading" | "success" | "expired";

function VerifyEmailInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  // Capture the token once, then strip it from the URL so it doesn't linger
  // in browser history or leak via the Referer header.
  const [token] = useState(() => searchParams.get("token") ?? "");

  const [state, setState] = useState<PageState>("loading");
  const [errorDetail, setErrorDetail] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setState("expired");
      setErrorDetail("Ссылка не содержит токен. Запросите новую из письма.");
      return;
    }
    router.replace("/verify-email");
    (async () => {
      try {
        await verifyEmail(token);
        setState("success");
      } catch (err) {
        setState("expired");
        setErrorDetail(
          err instanceof ApiError
            ? err.detail
            : "Ссылка недействительна или устарела.",
        );
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // run once on mount

  return (
    <div style={{ background: "#f1f5f9", minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: "20px 16px" }}>
      <div style={{ width: "100%", maxWidth: 440 }}>
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <Link href="/" style={{ fontSize: 26, fontWeight: 800, color: "#0B2545", textDecoration: "none", letterSpacing: "-0.5px" }}>Novex</Link>
        </div>

        <div style={{ background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 16, padding: 40, boxShadow: "0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)", textAlign: "center" }}>
          {state === "loading" && (
            <>
              <div style={{ width: 56, height: 56, borderRadius: "50%", background: "#F1F5F9", border: "2px solid #CFDCEA", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px", fontSize: 24 }}>
                ⏳
              </div>
              <h1 style={{ margin: "0 0 10px", fontSize: 20, fontWeight: 700, color: "#0B2545" }}>Подтверждаем email…</h1>
              <p style={{ margin: 0, fontSize: 14, color: "#64748b" }}>Секунду, проверяем ссылку.</p>
            </>
          )}

          {state === "success" && (
            <>
              <div style={{ width: 56, height: 56, borderRadius: "50%", background: "#f0fdf4", border: "2px solid #bbf7d0", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px", fontSize: 24, color: "#166534" }}>
                ✓
              </div>
              <h1 style={{ margin: "0 0 10px", fontSize: 20, fontWeight: 700, color: "#0B2545" }}>Email подтверждён</h1>
              <p style={{ margin: "0 0 24px", fontSize: 14, color: "#64748b" }}>
                Аккаунт активирован. Теперь вы можете оформлять заказы и оплачивать их.
              </p>
              <button
                onClick={() => router.push("/dashboard")}
                style={{ padding: "12px 28px", borderRadius: 10, border: "none", background: "#0B2545", color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "#163558"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "#0B2545"; }}
              >
                Перейти в личный кабинет →
              </button>
            </>
          )}

          {state === "expired" && (
            <>
              <div style={{ width: 56, height: 56, borderRadius: "50%", background: "#fef2f2", border: "2px solid #fecaca", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px", fontSize: 24, color: "#b91c1c" }}>
                ✕
              </div>
              <h1 style={{ margin: "0 0 10px", fontSize: 20, fontWeight: 700, color: "#0B2545" }}>Ссылка недействительна</h1>
              <p style={{ margin: "0 0 24px", fontSize: 14, color: "#64748b" }}>
                {errorDetail ?? "Возможно, вы уже её использовали или срок действия истёк."}
                <br />
                Войдите в аккаунт и отправьте письмо повторно.
              </p>
              <button
                onClick={() => router.push("/login")}
                style={{ padding: "12px 28px", borderRadius: 10, border: "none", background: "#0B2545", color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "#163558"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "#0B2545"; }}
              >
                Войти
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return <Suspense><VerifyEmailInner /></Suspense>;
}
