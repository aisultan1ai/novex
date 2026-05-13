"use client";

import { useState } from "react";

type Method = "POST" | "GET";

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
    title: "Отправить трекинг-событие",
    auth: "HMAC-SHA256 подпись в заголовке X-Carrier-Signature",
    description: "Вызывайте этот endpoint каждый раз, когда статус отправления меняется. Novex обновит статус заказа и отправит push-уведомление клиенту.",
    requestBody: JSON.stringify({
      novex_order_id: 1042,
      status: "in_transit",
      location: "Алматы, сортировочный центр",
      description: "Посылка передана в транзит",
      occurred_at: "2026-05-13T10:30:00Z",
    }, null, 2),
    responseBody: JSON.stringify({ ok: true }, null, 2),
    notes: "Если novex_order_id не найден - возвращаем 200 OK без ошибки (идемпотентно).",
  },
  {
    method: "POST",
    path: "YOUR_PUSH_URL (настраивается администратором)",
    title: "Принять заказ от Novex",
    auth: "Проверьте HMAC-SHA256 подпись из заголовка X-Novex-Signature",
    description: "Novex вызовет ваш API автоматически после оплаты заказа клиентом. Вам нужно обработать заказ и вернуть трекинг-номер.",
    requestBody: JSON.stringify({
      novex_order_id: 1042,
      tariff_code: "STANDARD",
      sender: { city: "Алматы", address: "ул. Абая, 1", full_name: "Магазин", phone: "+77001112233" },
      recipient: { city: "Астана", address: "пр. Мангилик Ел, 55", full_name: "Иван Иванов", phone: "+77009998877" },
      packages: [{ weight_kg: 2.5, length_cm: 30, width_cm: 20, height_cm: 15 }],
      declared_value: 15000,
      currency: "KZT",
    }, null, 2),
    responseBody: JSON.stringify({ tracking_number: "AZM-20260513-1042" }, null, 2),
    notes: "Ответ должен прийти в течение timeout_seconds (по умолчанию 10 с). При ошибке Novex повторит запрос retry_count раз.",
  },
];

const STATUSES = [
  { code: "picked_up",          desc: "Курьер забрал посылку у отправителя" },
  { code: "in_transit",         desc: "Посылка в пути / на сортировке" },
  { code: "out_for_delivery",   desc: "Курьер выехал к получателю" },
  { code: "delivered",          desc: "Доставлено - заказ закрыт" },
  { code: "failed_attempt",     desc: "Попытка доставки не удалась" },
  { code: "returned",           desc: "Возврат отправителю" },
  { code: "cancelled",          desc: "Отправление отменено" },
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
    "status": "delivered",
    "location": "Астана, пр. Мангилик Ел",
    "description": "Посылка вручена получателю",
    "occurred_at": "2026-05-13T15:00:00Z",
}
body = json.dumps(payload, ensure_ascii=False).encode()
sig  = sign(body, SECRET)

resp = requests.post(
    NOVEX_WEBHOOK,
    data=body,
    headers={"Content-Type": "application/json", "X-Carrier-Signature": sig},
)
print(resp.status_code, resp.json())`,

  nodejs: `const crypto = require('crypto');

const SECRET = 'ваш_webhook_secret';
const NOVEX_WEBHOOK = 'https://api.novex.kz/api/v1/carriers/YOUR_CODE/tracking-webhook';

const payload = {
  novex_order_id: 1042,
  status: 'delivered',
  location: 'Астана, пр. Мангилик Ел',
  description: 'Посылка вручена получателю',
  occurred_at: new Date().toISOString(),
};

const body = JSON.stringify(payload);
const sig  = crypto.createHmac('sha256', SECRET).update(body).digest('hex');

fetch(NOVEX_WEBHOOK, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-Carrier-Signature': sig },
  body,
}).then(r => r.json()).then(console.log);`,

  verify: `# Проверка подписи входящего запроса от Novex (Python)
import hashlib, hmac

def verify_novex_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

# В вашем обработчике:
# sig = request.headers.get("X-Novex-Signature", "")
# if not verify_novex_signature(request.body, sig, SECRET):
#     return {"error": "Invalid signature"}, 401`,
};

function EndpointCard({ ep }: { ep: Endpoint }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 14, overflow: "hidden", marginBottom: 12 }}>
      <div style={{ padding: "16px 20px", cursor: "pointer", display: "flex", alignItems: "center", gap: 12, userSelect: "none" }} onClick={() => setOpen((v) => !v)}>
        <span style={{ fontFamily: "monospace", fontWeight: 700, fontSize: 12, padding: "3px 10px", borderRadius: 6, background: "#dcfce7", color: "#166534", flexShrink: 0 }}>{ep.method}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>{ep.title}</div>
          <code style={{ fontSize: 12, fontFamily: "monospace", color: "#64748b" }}>{ep.path}</code>
        </div>
        <span style={{ color: "#94a3b8", fontSize: 12 }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div style={{ padding: "0 20px 20px", display: "flex", flexDirection: "column", gap: 14, borderTop: "1px solid #f1f5f9" }}>
          <p style={{ margin: "12px 0 0", fontSize: 14, color: "#334155" }}>{ep.description}</p>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: "#64748b", minWidth: 56 }}>Auth:</span>
            <code style={{ fontSize: 12, background: "#fdf4ff", color: "#9333ea", padding: "3px 8px", borderRadius: 6, fontFamily: "monospace" }}>{ep.auth}</code>
          </div>
          {ep.requestBody && (
            <div>
              <p style={{ margin: "0 0 8px", fontSize: 12, fontWeight: 600, color: "#64748b" }}>Request body:</p>
              <pre style={{ margin: 0, padding: "14px 16px", background: "#0f172a", borderRadius: 10, color: "#e2e8f0", fontSize: 12, overflow: "auto", lineHeight: 1.6 }}>{ep.requestBody}</pre>
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
              {ep.notes}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function CarrierDocsPage() {
  const [lang, setLang] = useState<"python" | "nodejs" | "verify">("python");

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0f172a" }}>API Документация</h2>
        <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>Руководство по интеграции с платформой Novex</p>
      </div>

      {/* Endpoints */}
      <section style={{ marginBottom: 28 }}>
        <h3 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 700, color: "#0f172a" }}>Endpoints</h3>
        {ENDPOINTS.map((ep) => <EndpointCard key={ep.path} ep={ep} />)}
      </section>

      {/* Status table */}
      <section style={{ marginBottom: 28 }}>
        <h3 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 700, color: "#0f172a" }}>Статусы трекинга</h3>
        <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 14, overflow: "hidden" }}>
          {STATUSES.map((s, i) => (
            <div key={s.code} style={{ display: "flex", alignItems: "center", gap: 16, padding: "12px 20px", borderBottom: i < STATUSES.length - 1 ? "1px solid #f1f5f9" : "none" }}>
              <code style={{ fontFamily: "monospace", fontSize: 13, background: "#f1f5f9", padding: "3px 10px", borderRadius: 6, color: "#0f172a", minWidth: 180, flexShrink: 0 }}>{s.code}</code>
              <span style={{ fontSize: 13, color: "#475569" }}>{s.desc}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Code examples */}
      <section>
        <h3 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 700, color: "#0f172a" }}>Примеры кода</h3>
        <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 14, overflow: "hidden" }}>
          <div style={{ display: "flex", gap: 0, borderBottom: "1px solid #e5e7eb" }}>
            {(["python", "nodejs", "verify"] as const).map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                style={{ padding: "10px 20px", background: lang === l ? "#0f172a" : "transparent", color: lang === l ? "#ffffff" : "#64748b", border: "none", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
              >
                {l === "python" ? "Python" : l === "nodejs" ? "Node.js" : "Проверка подписи"}
              </button>
            ))}
          </div>
          <pre style={{ margin: 0, padding: "20px 24px", background: "#0f172a", color: "#e2e8f0", fontSize: 13, overflow: "auto", lineHeight: 1.7 }}>
            {CODE_EXAMPLES[lang]}
          </pre>
        </div>
      </section>
    </>
  );
}
