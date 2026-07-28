"use client";

import { useEffect, useState } from "react";

import { getIntegrationConfig } from "@/lib/api/carrier";
import type { IntegrationConfig } from "@/types/carrier";

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { void navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); }); }}
      style={{ background: "none", border: "1px solid #e5e7eb", borderRadius: 6, padding: "4px 10px", fontSize: 12, cursor: "pointer", color: copied ? "#16a34a" : "#64748b", fontFamily: "inherit" }}
    >
      {copied ? "Скопировано" : "Копировать"}
    </button>
  );
}

function SecretField({ value }: { value: string | null }) {
  const [visible, setVisible] = useState(false);
  if (!value) return <span style={{ fontSize: 13, color: "#f97316" }}>не настроен - обратитесь к администратору</span>;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <code style={{ fontSize: 13, fontFamily: "monospace", color: "#0f172a", background: "#f8fafc", padding: "4px 10px", borderRadius: 6, flex: 1 }}>
        {visible ? value : "••••••••••••••••••••••••"}
      </code>
      <button onClick={() => setVisible((v) => !v)} style={{ background: "none", border: "1px solid #e5e7eb", borderRadius: 6, padding: "4px 10px", fontSize: 12, cursor: "pointer", color: "#64748b", fontFamily: "inherit" }}>
        {visible ? "Скрыть" : "Показать"}
      </button>
      {visible && <CopyBtn text={value} />}
    </div>
  );
}

export default function IntegrationPage() {
  const [config, setConfig] = useState<IntegrationConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getIntegrationConfig()
      .then(setConfig)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <div style={{ padding: "16px 20px", borderRadius: 12, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", fontSize: 14 }}>{error}</div>;
  if (!config) return <div style={{ padding: 48, textAlign: "center", color: "#94a3b8" }}>Загружаем...</div>;

  const { outbound, inbound } = config.methods;

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0f172a" }}>Настройка интеграции</h2>
        <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>Два метода работы с Novex - оба активны одновременно</p>
      </div>

      {/* Method 1: Outbound (Novex → Carrier) */}
      <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "hidden", marginBottom: 16 }}>
        <div style={{ padding: "16px 24px", borderBottom: "1px solid #f1f5f9", display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ padding: "4px 12px", borderRadius: 999, background: "#dcfce7", color: "#166534", fontSize: 12, fontWeight: 700 }}>POST</div>
          <div>
            <span style={{ fontSize: 15, fontWeight: 700, color: "#0f172a" }}>Novex → Ваш API</span>
            <span style={{ fontSize: 13, color: "#64748b", marginLeft: 8 }}>(push-отправка заказов)</span>
          </div>
          <div style={{ marginLeft: "auto", padding: "3px 10px", borderRadius: 999, background: outbound.active ? "#dcfce7" : "#fef9c3", color: outbound.active ? "#166534" : "#a16207", fontSize: 12, fontWeight: 600 }}>
            {outbound.active ? "Активен" : "Не настроен"}
          </div>
        </div>
        <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
          <p style={{ margin: 0, fontSize: 14, color: "#334155" }}>
            При оплате заказа Novex автоматически вызовет ваш API и передаст данные отправления. В ответ ожидается <code style={{ fontFamily: "monospace", fontSize: 13, background: "#f1f5f9", padding: "1px 6px", borderRadius: 4 }}>tracking_number</code>.
          </p>

          <ConfigRow label="Ваш endpoint (push_url)">
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <code style={{ fontSize: 13, fontFamily: "monospace", color: "#0f172a", background: "#f8fafc", padding: "4px 10px", borderRadius: 6, flex: 1 }}>
                {outbound.novex_calls_your_url || "не задан"}
              </code>
              {outbound.novex_calls_your_url && <CopyBtn text={outbound.novex_calls_your_url} />}
            </div>
          </ConfigRow>

          <ConfigRow label="HMAC заголовок">
            <code style={{ fontSize: 13, fontFamily: "monospace", color: "#0f172a", background: "#f8fafc", padding: "4px 10px", borderRadius: 6 }}>{outbound.hmac_header}</code>
          </ConfigRow>

          <ConfigRow label="Секретный ключ (для проверки подписи)">
            <SecretField value={outbound.secret_key} />
          </ConfigRow>

          <ConfigRow label="Формат подписи">
            <span style={{ fontSize: 13, color: "#334155" }}>
              <code style={{ fontFamily: "monospace", fontSize: 13, background: "#f1f5f9", padding: "2px 6px", borderRadius: 4 }}>HMAC-SHA256(secret, timestamp + raw_body)</code> → hex → заголовок <code style={{ fontFamily: "monospace", fontSize: 13, background: "#f1f5f9", padding: "2px 6px", borderRadius: 4 }}>{outbound.hmac_header}</code>
              <br />
              <span style={{ fontSize: 12, color: "#64748b" }}>
                Строка для подписи — конкатенация значения заголовка <code style={{ fontFamily: "monospace", fontSize: 12, background: "#f1f5f9", padding: "1px 5px", borderRadius: 4 }}>X-Novex-Timestamp</code> и байтов тела без разделителя.
              </span>
            </span>
          </ConfigRow>

          <ConfigRow label="Обязательные заголовки">
            <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, color: "#334155" }}>
              <div><code style={{ fontFamily: "monospace", fontSize: 13, background: "#f1f5f9", padding: "2px 6px", borderRadius: 4 }}>X-Novex-Timestamp</code> — unix-time (сек). Проверяйте окно ±5 мин для защиты от replay.</div>
              <div><code style={{ fontFamily: "monospace", fontSize: 13, background: "#f1f5f9", padding: "2px 6px", borderRadius: 4 }}>X-Novex-Event-Id</code> — UUID запроса. Используйте для идемпотентности повторов.</div>
              <div><code style={{ fontFamily: "monospace", fontSize: 13, background: "#f1f5f9", padding: "2px 6px", borderRadius: 4 }}>X-Novex-Platform</code> — всегда <code style={{ fontFamily: "monospace", fontSize: 12 }}>novex-logistics</code>.</div>
            </div>
          </ConfigRow>

          <details style={{ cursor: "pointer" }}>
            <summary style={{ fontSize: 13, fontWeight: 600, color: "#4338ca", userSelect: "none" }}>Пример тела запроса от Novex</summary>
            <pre style={{ margin: "12px 0 0", padding: "16px", background: "#0f172a", borderRadius: 10, color: "#e2e8f0", fontSize: 12, overflow: "auto", lineHeight: 1.6 }}>{JSON.stringify({
              novex_order_id: 1042,
              order_reference: "NOVEX-001042",
              tariff_code: "STANDARD",
              sender: {
                full_name: "Магазин Novex",
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
            }, null, 2)}</pre>
          </details>

          <details style={{ cursor: "pointer" }}>
            <summary style={{ fontSize: 13, fontWeight: 600, color: "#4338ca", userSelect: "none" }}>Ожидаемый ответ от вашего API</summary>
            <pre style={{ margin: "12px 0 0", padding: "16px", background: "#0f172a", borderRadius: 10, color: "#e2e8f0", fontSize: 12, overflow: "auto" }}>{JSON.stringify({
              tracking_number: "AZM-20260513-1042",
              barcode: "AZM-BC-20260513-1042",
            }, null, 2)}</pre>
            <p style={{ margin: "8px 0 0", font: "400 12px/1.5 Inter Variable, sans-serif", color: "#64748b" }}>
              tracking_number обязателен. barcode (или carrier_invoice_id) — опциональное физическое штрих-код на этикетке.
            </p>
          </details>
        </div>
      </div>

      {/* Method 2: Inbound (Carrier → Novex) */}
      <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "hidden" }}>
        <div style={{ padding: "16px 24px", borderBottom: "1px solid #f1f5f9", display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ padding: "4px 12px", borderRadius: 999, background: "#dcfce7", color: "#166534", fontSize: 12, fontWeight: 700 }}>POST</div>
          <div>
            <span style={{ fontSize: 15, fontWeight: 700, color: "#0f172a" }}>Ваш API → Novex</span>
            <span style={{ fontSize: 13, color: "#64748b", marginLeft: 8 }}>(push трекинг-событий)</span>
          </div>
          <div style={{ marginLeft: "auto", padding: "3px 10px", borderRadius: 999, background: "#dcfce7", color: "#166534", fontSize: 12, fontWeight: 600 }}>Активен</div>
        </div>
        <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
          <p style={{ margin: 0, fontSize: 14, color: "#334155" }}>
            Когда статус отправления меняется - отправьте нам событие. Мы обновим статус заказа и уведомим клиента.
          </p>

          <ConfigRow label="Наш webhook endpoint">
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <code style={{ fontSize: 13, fontFamily: "monospace", color: "#0f172a", background: "#f8fafc", padding: "4px 10px", borderRadius: 6, flex: 1 }}>
                POST {inbound.your_calls_our_url}
              </code>
              <CopyBtn text={inbound.your_calls_our_url} />
            </div>
          </ConfigRow>

          <ConfigRow label="HMAC заголовок">
            <code style={{ fontSize: 13, fontFamily: "monospace", color: "#0f172a", background: "#f8fafc", padding: "4px 10px", borderRadius: 6 }}>{inbound.hmac_header}</code>
          </ConfigRow>

          <ConfigRow label="Секретный ключ (для подписи)">
            <SecretField value={inbound.secret_key} />
          </ConfigRow>

          <details style={{ cursor: "pointer" }}>
            <summary style={{ fontSize: 13, fontWeight: 600, color: "#4338ca", userSelect: "none" }}>Пример тела запроса (ваш запрос к нам)</summary>
            <pre style={{ margin: "12px 0 0", padding: "16px", background: "#0f172a", borderRadius: 10, color: "#e2e8f0", fontSize: 12, overflow: "auto", lineHeight: 1.6 }}>{JSON.stringify({
              novex_order_id: 1042,
              status: "IN_TRANSIT",
              location: "Алматы сортировочный центр",
              description: "Посылка принята и передана в транзит",
              event_id: "opt-uuid-for-dedup",
            }, null, 2)}</pre>
            <p style={{ margin: "8px 0 0", font: "400 12px/1.5 Inter Variable, sans-serif", color: "#64748b" }}>
              event_id опционален — используется для идемпотентности (если ретраите, ставьте один и тот же). Обязательные заголовки: <code>X-Novex-Timestamp</code> (unix-time, окно ±5 мин) и <code>X-Carrier-Signature</code> (HMAC-SHA256 от body).
            </p>
          </details>

          <details style={{ cursor: "pointer" }}>
            <summary style={{ fontSize: 13, fontWeight: 600, color: "#4338ca", userSelect: "none" }}>Допустимые значения статуса</summary>
            <div style={{ margin: "12px 0 0", display: "flex", flexWrap: "wrap", gap: 8 }}>
              {["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "ARRIVED", "DELIVERED", "FAILED_ATTEMPT", "CUSTOMS_HOLD", "RETURNED", "CANCELLED"].map((s) => (
                <span key={s} style={{ fontFamily: "monospace", fontSize: 12, padding: "3px 10px", borderRadius: 6, background: "#f1f5f9", color: "#0f172a" }}>{s}</span>
              ))}
            </div>
            <p style={{ margin: "8px 0 0", font: "400 12px/1.5 Inter Variable, sans-serif", color: "#64748b" }}>
              Регистронезависимо. Неизвестный статус трактуется как <code>IN_TRANSIT</code> и логируется, чтобы мы добавили маппинг.
            </p>
          </details>
        </div>
      </div>
    </>
  );
}

function ConfigRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: 12, alignItems: "start" }}>
      <span style={{ fontSize: 13, fontWeight: 600, color: "#64748b", paddingTop: 4 }}>{label}</span>
      <div>{children}</div>
    </div>
  );
}
