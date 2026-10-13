"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

type Method = "POST" | "GET";

// Текстовые поля (title/description/auth/notes, path у push) - ключи перевода
// carrier.docs.*; технические пути и примеры кода не переводятся.
interface Endpoint {
  method: Method;
  path: string;
  title: string;
  description: string;
  auth: string;
  requestBody?: string;
  responseBody?: string;
  notes?: string;
}

const ENDPOINTS: Endpoint[] = [
  {
    method: "POST",
    path: "/api/v1/carriers/{carrier_code}/tracking-webhook",
    title: "endpoints.webhook.title",
    auth: "endpoints.webhook.auth",
    description: "endpoints.webhook.description",
    requestBody: JSON.stringify({
      novex_order_id: 1042,
      status: "IN_TRANSIT",
      location: "Алматы, сортировочный центр",
      description: "Посылка передана в транзит",
      event_id: "opt-uuid-for-dedup",
    }, null, 2),
    responseBody: JSON.stringify({ ok: true }, null, 2),
    notes: "endpoints.webhook.notes",
  },
  {
    method: "POST",
    path: "endpoints.push.path",
    title: "endpoints.push.title",
    auth: "endpoints.push.auth",
    description: "endpoints.push.description",
    requestBody: JSON.stringify({
      novex_order_id: 1042,
      order_reference: "NOVEX-001042",
      tariff_code: "STANDARD",
      sender: {
        full_name: "Магазин",
        phone: "+77001112233",
        city: "Алматы",
        address: "ул. Абая, 1",
        tax_id: "123456789012",
      },
      recipient: {
        full_name: "Иван Иванов",
        phone: "+77009998877",
        city: "Астана",
        address: "пр. Мангилик Ел, 55",
        tax_id: "210987654321",
      },
      packages: [{
        weight_kg: 2.5,
        width_cm: 20,
        height_cm: 15,
        depth_cm: 30,
        quantity: 1,
      }],
      declared_value: 15000,
      currency: "KZT",
      additional_services: {
        call_before_delivery: false,
        insurance: false,
        fragile: false,
      },
    }, null, 2),
    responseBody: JSON.stringify({
      tracking_number: "AZM-20260513-1042",
      barcode: "AZM-BC-20260513-1042",
    }, null, 2),
    notes: "endpoints.push.notes",
  },
];

const STATUSES = [
  // desc - carrier.docs.statuses.<code>
  { code: "PICKED_UP" },
  { code: "IN_TRANSIT" },
  { code: "OUT_FOR_DELIVERY" },
  { code: "ARRIVED" },
  { code: "DELIVERED" },
  { code: "FAILED_ATTEMPT" },
  { code: "CUSTOMS_HOLD" },
  { code: "RETURNED" },
  { code: "CANCELLED" },
];

const CODE_EXAMPLES = {
  python: `import hashlib, hmac, json, time
import requests

SECRET = "ваш_webhook_secret"
NOVEX_WEBHOOK = "https://api.novex.kz/api/v1/carriers/YOUR_CODE/tracking-webhook"

def sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

payload = {
    "novex_order_id": 1042,
    "status": "DELIVERED",
    "location": "Астана, пр. Мангилик Ел",
    "description": "Посылка вручена получателю",
}
body = json.dumps(payload, ensure_ascii=False).encode()
sig  = sign(body, SECRET)
ts   = str(int(time.time()))

resp = requests.post(
    NOVEX_WEBHOOK,
    data=body,
    headers={
        "Content-Type": "application/json",
        "X-Carrier-Signature": sig,
        "X-Novex-Timestamp": ts,  # обязательный для anti-replay (окно ±5 мин)
    },
)
print(resp.status_code, resp.json())`,

  nodejs: `const crypto = require('crypto');

const SECRET = 'ваш_webhook_secret';
const NOVEX_WEBHOOK = 'https://api.novex.kz/api/v1/carriers/YOUR_CODE/tracking-webhook';

const payload = {
  novex_order_id: 1042,
  status: 'DELIVERED',
  location: 'Астана, пр. Мангилик Ел',
  description: 'Посылка вручена получателю',
};

const body = JSON.stringify(payload);
const sig  = crypto.createHmac('sha256', SECRET).update(body).digest('hex');
const ts   = String(Math.floor(Date.now() / 1000));

fetch(NOVEX_WEBHOOK, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Carrier-Signature': sig,
    'X-Novex-Timestamp': ts,  // обязательный для anti-replay (окно ±5 мин)
  },
  body,
}).then(r => r.json()).then(console.log);`,

  verify: `# Проверка подписи входящего запроса от Novex (Python)
import hashlib, hmac, time

SECRET = "ваш_webhook_secret"
REPLAY_WINDOW_SECONDS = 300  # окно ±5 мин

def verify_novex_signature(body: bytes, timestamp: str, signature: str, secret: str) -> bool:
    # 1. Anti-replay: timestamp обязателен и должен попадать в окно ±5 мин
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(time.time() - ts) > REPLAY_WINDOW_SECONDS:
        return False

    # 2. Подпись считается от конкатенации timestamp + raw_body
    sig_input = (timestamp + body.decode()).encode()
    expected = hmac.new(secret.encode(), sig_input, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

# В вашем обработчике:
# ts  = request.headers.get("X-Novex-Timestamp", "")
# sig = request.headers.get("X-Novex-Signature", "")
# if not verify_novex_signature(request.body, ts, sig, SECRET):
#     return {"error": "Invalid signature or expired timestamp"}, 401
#
# Идемпотентность: X-Novex-Event-Id - сохраните и игнорируйте повторы.`,
};

function EndpointCard({ ep }: { ep: Endpoint }) {
  const t = useTranslations("carrier.docs");
  // Ключ перевода → текст; обычный путь (/api/v1/...) остаётся как есть.
  const tx = (s: string) => (t.has(s) ? t(s) : s);
  const [open, setOpen] = useState(false);
  return (
    <div style={{ background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 14, overflow: "hidden", marginBottom: 12 }}>
      <div style={{ padding: "16px 20px", cursor: "pointer", display: "flex", alignItems: "center", gap: 12, userSelect: "none" }} onClick={() => setOpen((v) => !v)}>
        <span style={{ fontFamily: "monospace", fontWeight: 700, fontSize: 12, padding: "3px 10px", borderRadius: 6, background: "#dcfce7", color: "#166534", flexShrink: 0 }}>{ep.method}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#0B2545" }}>{tx(ep.title)}</div>
          <code style={{ fontSize: 12, fontFamily: "monospace", color: "#64748b" }}>{tx(ep.path)}</code>
        </div>
        <span style={{ color: "#94a3b8", fontSize: 12 }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div style={{ padding: "0 20px 20px", display: "flex", flexDirection: "column", gap: 14, borderTop: "1px solid #f1f5f9" }}>
          <p style={{ margin: "12px 0 0", fontSize: 14, color: "#334155" }}>{tx(ep.description)}</p>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: "#64748b", minWidth: 56 }}>Auth:</span>
            <code style={{ fontSize: 12, background: "#fdf4ff", color: "#9333ea", padding: "3px 8px", borderRadius: 6, fontFamily: "monospace" }}>{tx(ep.auth)}</code>
          </div>
          {ep.requestBody && (
            <div>
              <p style={{ margin: "0 0 8px", fontSize: 12, fontWeight: 600, color: "#64748b" }}>Request body:</p>
              <pre style={{ margin: 0, padding: "14px 16px", background: "#0B2545", borderRadius: 10, color: "#e2e8f0", fontSize: 12, overflow: "auto", lineHeight: 1.6 }}>{ep.requestBody}</pre>
            </div>
          )}
          {ep.responseBody && (
            <div>
              <p style={{ margin: "0 0 8px", fontSize: 12, fontWeight: 600, color: "#64748b" }}>Response:</p>
              <pre style={{ margin: 0, padding: "14px 16px", background: "#052e16", borderRadius: 10, color: "#bbf7d0", fontSize: 12, overflow: "auto" }}>{ep.responseBody}</pre>
            </div>
          )}
          {ep.notes && (
            <div style={{ padding: "10px 14px", background: "#fffbeb", borderRadius: 8, border: "1px solid #fde68a", fontSize: 13, color: "#92400e" }}>
              {tx(ep.notes)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function CarrierDocsPage() {
  const t = useTranslations("carrier.docs");
  const [lang, setLang] = useState<"python" | "nodejs" | "verify">("python");

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0B2545" }}>{t("title")}</h2>
        <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>{t("subtitle")}</p>
      </div>

      {/* Endpoints */}
      <section style={{ marginBottom: 28 }}>
        <h3 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 700, color: "#0B2545" }}>Endpoints</h3>
        {ENDPOINTS.map((ep) => <EndpointCard key={ep.path} ep={ep} />)}
      </section>

      {/* Status table */}
      <section style={{ marginBottom: 28 }}>
        <h3 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 700, color: "#0B2545" }}>{t("statusesTitle")}</h3>
        <div style={{ background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 14, overflow: "hidden" }}>
          {STATUSES.map((s, i) => (
            <div key={s.code} style={{ display: "flex", alignItems: "center", gap: 16, padding: "12px 20px", borderBottom: i < STATUSES.length - 1 ? "1px solid #f1f5f9" : "none" }}>
              <code style={{ fontFamily: "monospace", fontSize: 13, background: "#f1f5f9", padding: "3px 10px", borderRadius: 6, color: "#0B2545", minWidth: 180, flexShrink: 0 }}>{s.code}</code>
              <span style={{ fontSize: 13, color: "#475569" }}>{t(`statuses.${s.code}`)}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Code examples */}
      <section>
        <h3 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 700, color: "#0B2545" }}>{t("codeTitle")}</h3>
        <div style={{ background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 14, overflow: "hidden" }}>
          <div style={{ display: "flex", gap: 0, borderBottom: "1px solid #E2E8EE" }}>
            {(["python", "nodejs", "verify"] as const).map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                style={{ padding: "10px 20px", background: lang === l ? "#0B2545" : "transparent", color: lang === l ? "#ffffff" : "#64748b", border: "none", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
              >
                {l === "python" ? "Python" : l === "nodejs" ? "Node.js" : t("verifyTab")}
              </button>
            ))}
          </div>
          <pre style={{ margin: 0, padding: "20px 24px", background: "#0B2545", color: "#e2e8f0", fontSize: 13, overflow: "auto", lineHeight: 1.7 }}>
            {CODE_EXAMPLES[lang]}
          </pre>
        </div>
      </section>
    </>
  );
}
