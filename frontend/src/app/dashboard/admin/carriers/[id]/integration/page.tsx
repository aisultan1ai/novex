"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import {
  getAdminCarrier,
  getCarrierIntegration,
  getCarrierIntegrationLogs,
  regenerateCarrierIntegrationSecret,
  testCarrierWebhook,
  updateCarrierIntegration,
  type CarrierIntegrationConfig,
  type CarrierIntegrationLogItem,
} from "@/lib/api/admin";
import type { AdminCarrierDetail } from "@/types/admin";

const inp: React.CSSProperties = {
  border: "1px solid #e5e7eb", borderRadius: 8, padding: "8px 12px",
  fontSize: 13, width: "100%", boxSizing: "border-box",
  fontFamily: "inherit", outline: "none", background: "#f8fafc", color: "#0f172a",
};
const lbl: React.CSSProperties = {
  display: "block", fontSize: 12, fontWeight: 600, color: "#64748b",
  marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.04em",
};

const DISPATCH_MODES = [
  { value: "auto", label: "Auto (API → Webhook fallback)" },
  { value: "api", label: "API only" },
  { value: "webhook", label: "Webhook (Generic) only" },
  { value: "manual", label: "Manual (no auto-dispatch)" },
];
const TRACKING_MODES = [
  { value: "webhook", label: "Webhook (carrier pushes status)" },
  { value: "polling", label: "Polling (Novex pulls status)" },
  { value: "manual", label: "Manual" },
];

export default function CarrierIntegrationPage() {
  const { id } = useParams<{ id: string }>();
  const carrierId = Number(id);

  const [carrier, setCarrier] = useState<AdminCarrierDetail | null>(null);
  const [cfg, setCfg] = useState<CarrierIntegrationConfig | null>(null);
  const [logs, setLogs] = useState<CarrierIntegrationLogItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [form, setForm] = useState({
    push_url: "",
    is_active: true,
    retry_count: 3,
    timeout_seconds: 10,
    dispatch_mode: "auto",
    tracking_mode: "webhook",
  });
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<{ text: string; ok: boolean } | null>(null);

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; duration_ms?: number; http_status?: number; response?: string; error?: string } | null>(null);

  const [regenSecret, setRegenSecret] = useState<string | null>(null);
  const [regenLoading, setRegenLoading] = useState(false);

  const [logsLoading, setLogsLoading] = useState(false);

  useEffect(() => {
    Promise.all([
      getAdminCarrier(carrierId),
      getCarrierIntegration(carrierId),
    ]).then(([c, integration]) => {
      setCarrier(c);
      setCfg(integration);
      setForm({
        push_url: integration.push_url ?? "",
        is_active: integration.is_active,
        retry_count: integration.retry_count,
        timeout_seconds: integration.timeout_seconds,
        dispatch_mode: integration.dispatch_mode ?? "auto",
        tracking_mode: integration.tracking_mode ?? "webhook",
      });
    }).finally(() => setLoading(false));
  }, [carrierId]);

  const loadLogs = async () => {
    setLogsLoading(true);
    try {
      const r = await getCarrierIntegrationLogs(carrierId, 50);
      setLogs(r.items);
    } finally {
      setLogsLoading(false);
    }
  };

  useEffect(() => { loadLogs(); }, [carrierId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaveMsg(null);
    try {
      const updated = await updateCarrierIntegration(carrierId, {
        push_url: form.push_url.trim() || undefined,
        is_active: form.is_active,
        retry_count: form.retry_count,
        timeout_seconds: form.timeout_seconds,
        dispatch_mode: form.dispatch_mode,
        tracking_mode: form.tracking_mode,
      });
      setCfg(updated);
      setSaveMsg({ text: "Настройки сохранены", ok: true });
    } catch (err: unknown) {
      setSaveMsg({ text: `Ошибка: ${(err as Error).message}`, ok: false });
    } finally {
      setSaving(false);
    }
  }

  async function handleTestWebhook() {
    setTesting(true);
    setTestResult(null);
    try {
      const r = await testCarrierWebhook(carrierId);
      setTestResult(r);
      await loadLogs();
    } catch (err: unknown) {
      setTestResult({ ok: false, duration_ms: 0, error: (err as Error).message });
    } finally {
      setTesting(false);
    }
  }

  async function handleRegenSecret() {
    if (!confirm("Сгенерировать новый webhook secret? Перевозчик должен будет обновить свой конфиг.")) return;
    setRegenLoading(true);
    setRegenSecret(null);
    try {
      const r = await regenerateCarrierIntegrationSecret(carrierId);
      setRegenSecret(r.webhook_secret);
      const updated = await getCarrierIntegration(carrierId);
      setCfg(updated);
    } catch (err: unknown) {
      setSaveMsg({ text: `Ошибка: ${(err as Error).message}`, ok: false });
    } finally {
      setRegenLoading(false);
    }
  }

  if (loading || !carrier) return <div style={{ padding: 40, color: "#64748b" }}>Загрузка…</div>;

  const dispatchStatus = form.dispatch_mode === "manual"
    ? { label: "Ручной режим", bg: "#fef9c3", color: "#854d0e" }
    : form.is_active
      ? { label: "Активна", bg: "#dcfce7", color: "#166534" }
      : { label: "Выключена", bg: "#fee2e2", color: "#991b1b" };

  return (
    <div style={{ maxWidth: 900 }}>
      {/* Breadcrumb */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 20, fontSize: 13 }}>
        <Link href="/dashboard/admin/carriers" style={{ color: "#64748b", textDecoration: "none" }}>Перевозчики</Link>
        <span style={{ color: "#d1d5db" }}>›</span>
        <Link href={`/dashboard/admin/carriers/${carrierId}`} style={{ color: "#64748b", textDecoration: "none" }}>{carrier.name}</Link>
        <span style={{ color: "#d1d5db" }}>›</span>
        <span style={{ color: "#0f172a", fontWeight: 600 }}>Интеграция</span>
      </div>

      {/* Header */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: "18px 24px", marginBottom: 20, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 800, color: "#0f172a" }}>{carrier.name}</div>
          <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>Настройки интеграции — Model A (API) + Model B (Generic Webhook)</div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span style={{ padding: "4px 12px", borderRadius: 999, fontSize: 12, fontWeight: 700, background: dispatchStatus.bg, color: dispatchStatus.color }}>
            {dispatchStatus.label}
          </span>
          {cfg?.last_success_at && (
            <span style={{ fontSize: 11, color: "#10b981" }}>
              Последний успех: {new Date(cfg.last_success_at).toLocaleString("ru-KZ")}
            </span>
          )}
        </div>
      </div>

      {cfg?.last_error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "10px 14px", fontSize: 13, color: "#991b1b", marginBottom: 16 }}>
          Последняя ошибка: {cfg.last_error}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 16, alignItems: "start" }}>
        {/* Main form */}
        <div>
          <form onSubmit={handleSave} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: "22px 24px", marginBottom: 16 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", marginBottom: 18 }}>Настройки диспетчеризации</div>

            {/* dispatch_mode */}
            <div style={{ marginBottom: 16 }}>
              <label style={lbl}>Режим диспетчеризации</label>
              <select value={form.dispatch_mode} onChange={(e) => setForm(f => ({ ...f, dispatch_mode: e.target.value }))} style={{ ...inp, cursor: "pointer" }}>
                {DISPATCH_MODES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
              <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>
                Auto: API если есть credentials, иначе Generic Webhook
              </div>
            </div>

            {/* tracking_mode */}
            <div style={{ marginBottom: 16 }}>
              <label style={lbl}>Режим трекинга</label>
              <select value={form.tracking_mode} onChange={(e) => setForm(f => ({ ...f, tracking_mode: e.target.value }))} style={{ ...inp, cursor: "pointer" }}>
                {TRACKING_MODES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </div>

            {/* push_url */}
            <div style={{ marginBottom: 16 }}>
              <label style={lbl}>Push URL (Model B — Generic Webhook)</label>
              <input
                style={inp}
                value={form.push_url}
                onChange={(e) => setForm(f => ({ ...f, push_url: e.target.value }))}
                placeholder="https://carrier.example.com/novex/orders"
              />
              <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>
                Novex отправит POST с заказом. Оставьте пустым для API-only перевозчика.
              </div>
            </div>

            {/* Webhook secret */}
            <div style={{ marginBottom: 16 }}>
              <label style={lbl}>Webhook Secret</label>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input style={{ ...inp, fontFamily: "monospace", flex: 1 }} readOnly value={cfg?.webhook_secret_masked ?? "Не задан"} />
                <button
                  type="button"
                  onClick={handleRegenSecret}
                  disabled={regenLoading}
                  style={{ whiteSpace: "nowrap", padding: "8px 14px", borderRadius: 8, border: "1px solid #e5e7eb", background: "#f8fafc", color: "#0f172a", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
                >
                  {regenLoading ? "…" : "Перегенерировать"}
                </button>
              </div>
              {regenSecret && (
                <div style={{ marginTop: 8, background: "#fefce8", border: "1px solid #fde68a", borderRadius: 8, padding: "10px 12px", fontSize: 12 }}>
                  <strong>Новый секрет (сохраните — показывается один раз):</strong>
                  <div style={{ fontFamily: "monospace", marginTop: 4, wordBreak: "break-all", color: "#0f172a" }}>{regenSecret}</div>
                </div>
              )}
            </div>

            <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
              <div style={{ flex: 1 }}>
                <label style={lbl}>Кол-во ретраев</label>
                <input type="number" min={1} max={10} style={inp} value={form.retry_count}
                  onChange={(e) => setForm(f => ({ ...f, retry_count: Number(e.target.value) }))} />
              </div>
              <div style={{ flex: 1 }}>
                <label style={lbl}>Таймаут (сек)</label>
                <input type="number" min={1} max={120} style={inp} value={form.timeout_seconds}
                  onChange={(e) => setForm(f => ({ ...f, timeout_seconds: Number(e.target.value) }))} />
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
              <input type="checkbox" id="is_active" checked={form.is_active} onChange={(e) => setForm(f => ({ ...f, is_active: e.target.checked }))} style={{ width: 16, height: 16, cursor: "pointer" }} />
              <label htmlFor="is_active" style={{ fontSize: 13, cursor: "pointer" }}>Интеграция активна</label>
            </div>

            {saveMsg && (
              <div style={{ padding: "10px 14px", borderRadius: 8, marginBottom: 14, fontSize: 13, background: saveMsg.ok ? "#f0fdf4" : "#fef2f2", color: saveMsg.ok ? "#166534" : "#b91c1c" }}>
                {saveMsg.text}
              </div>
            )}

            <button type="submit" disabled={saving} style={{ padding: "10px 24px", borderRadius: 10, border: "none", background: "#0f172a", color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
              {saving ? "Сохраняем…" : "Сохранить"}
            </button>
          </form>

          {/* Integration Logs */}
          <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: "20px 24px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: "#0f172a" }}>Журнал событий</div>
              <button onClick={loadLogs} disabled={logsLoading} style={{ fontSize: 12, color: "#4338ca", background: "none", border: "none", cursor: "pointer", fontWeight: 600 }}>
                {logsLoading ? "…" : "Обновить"}
              </button>
            </div>
            {logs.length === 0 ? (
              <p style={{ color: "#9ca3af", fontSize: 13 }}>Событий нет</p>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e5e7eb" }}>
                    {["Время", "Направление", "Тип", "Заказ", "HTTP", "Время мс", "Статус"].map(h => (
                      <th key={h} style={{ textAlign: "left", padding: "6px 10px", fontWeight: 600, color: "#374151", whiteSpace: "nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {logs.map(log => (
                    <tr key={log.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                      <td style={{ padding: "7px 10px", whiteSpace: "nowrap", color: "#6b7280" }}>{new Date(log.created_at).toLocaleString("ru-KZ")}</td>
                      <td style={{ padding: "7px 10px" }}>
                        <span style={{ padding: "2px 8px", borderRadius: 6, fontSize: 11, fontWeight: 600, background: log.direction === "outbound" ? "#dbeafe" : "#dcfce7", color: log.direction === "outbound" ? "#1e40af" : "#166534" }}>
                          {log.direction === "outbound" ? "→ OUT" : "← IN"}
                        </span>
                      </td>
                      <td style={{ padding: "7px 10px", color: "#374151" }}>{log.event_type}</td>
                      <td style={{ padding: "7px 10px", color: "#6b7280" }}>{log.order_id ? `#${log.order_id}` : "—"}</td>
                      <td style={{ padding: "7px 10px", color: "#6b7280" }}>{log.http_status ?? "—"}</td>
                      <td style={{ padding: "7px 10px", color: "#6b7280" }}>{log.duration_ms ?? "—"}</td>
                      <td style={{ padding: "7px 10px" }}>
                        <span style={{ padding: "2px 8px", borderRadius: 6, fontSize: 11, fontWeight: 600, background: log.status === "success" ? "#dcfce7" : "#fee2e2", color: log.status === "success" ? "#166534" : "#991b1b" }}>
                          {log.status}
                        </span>
                        {log.error_message && <div style={{ color: "#ef4444", fontSize: 11, marginTop: 2 }}>{log.error_message.slice(0, 80)}</div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Right panel */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Test webhook */}
          <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: "18px 20px" }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a", marginBottom: 10 }}>Тест Generic Webhook</div>
            <p style={{ fontSize: 12, color: "#64748b", marginBottom: 12, marginTop: 0 }}>
              Отправит тестовый заказ на push_url с HMAC подписью (X-Novex-Signature, X-Novex-Timestamp, X-Novex-Event-Id).
            </p>
            <button
              onClick={handleTestWebhook}
              disabled={testing || !form.push_url}
              style={{ width: "100%", padding: "10px", borderRadius: 10, border: "1px solid #e5e7eb", background: form.push_url ? "#f8fafc" : "#f1f5f9", color: form.push_url ? "#0f172a" : "#94a3b8", fontSize: 13, fontWeight: 600, cursor: form.push_url ? "pointer" : "not-allowed", fontFamily: "inherit" }}
            >
              {testing ? "Отправляем…" : "Отправить тестовый заказ"}
            </button>
            {testResult && (
              <div style={{ marginTop: 10, padding: "10px 12px", borderRadius: 8, fontSize: 12, background: testResult.ok ? "#f0fdf4" : "#fef2f2", color: testResult.ok ? "#166534" : "#b91c1c" }}>
                {testResult.ok ? "✓ Успех" : "✗ Ошибка"}
                {testResult.http_status && <span> — HTTP {testResult.http_status}</span>}
                {testResult.duration_ms && <span> — {testResult.duration_ms}ms</span>}
                {testResult.error && <div style={{ marginTop: 4 }}>{testResult.error}</div>}
                {testResult.response && <div style={{ marginTop: 4, fontFamily: "monospace", wordBreak: "break-all" }}>{testResult.response.slice(0, 200)}</div>}
              </div>
            )}
          </div>

          {/* How it works */}
          <div style={{ background: "#f8fafc", border: "1px solid #e5e7eb", borderRadius: 14, padding: "16px 18px" }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#0f172a", marginBottom: 10 }}>Как работает диспетчеризация</div>
            <div style={{ fontSize: 12, color: "#475569", lineHeight: 1.7 }}>
              <div style={{ marginBottom: 8 }}>
                <span style={{ fontWeight: 600 }}>Model A (API Adapter)</span><br />
                Carrier имеет REST API. Novex вызывает его напрямую. Настраивается на вкладке API.
              </div>
              <div>
                <span style={{ fontWeight: 600 }}>Model B (Generic Webhook)</span><br />
                Carrier принимает POST на свой URL. Novex подписывает запрос HMAC-SHA256. Не нужен Python-код — достаточно настроить push_url и secret.
              </div>
            </div>
          </div>

          {/* Webhook endpoints */}
          <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 14, padding: "16px 18px" }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#0f172a", marginBottom: 10 }}>Endpoint для трекинга</div>
            <div style={{ fontFamily: "monospace", fontSize: 11, background: "#f1f5f9", padding: "8px 10px", borderRadius: 6, wordBreak: "break-all", color: "#334155" }}>
              POST /api/v1/carriers/{carrier.code}/tracking-webhook
            </div>
            <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 6 }}>
              Carrier отправляет статусы сюда. Требуется: X-Carrier-Signature, X-Novex-Timestamp.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
