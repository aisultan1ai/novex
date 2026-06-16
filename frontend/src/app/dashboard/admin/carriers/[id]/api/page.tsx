"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import {
  deleteCarrierAPICredentials,
  getAdminCarrier,
  getCarrierAPICredentials,
  testCarrierAPIConnection,
  upsertCarrierAPICredentials,
  type CarrierAPICredentials,
} from "@/lib/api/admin";
import type { AdminCarrierDetail } from "@/types/admin";

const CARRIER_DEFAULTS: Record<string, { api_url: string; extra_config: Record<string, unknown>; hint: string }> = {
  azimuth: {
    api_url: "https://api.azimuthcargo.kz",
    extra_config: { service_type: 2, payment_type: 2, payer: 1, payer_tin: "" },
    hint: "service_type (1=Авто, 2=Авиа), payment_type, payer (1=Отправитель, 2=Получатель), payer_tin",
  },
  exline: {
    api_url: "https://home.courierexe.ru/api/",
    extra_config: { extra: "", login: "", password: "" },
    hint: "extra — идентификатор компании в MeaSoft, login — логин, password — пароль",
  },
};

const FALLBACK_DEFAULTS = { api_url: "", extra_config: {}, hint: "Дополнительные параметры в формате JSON" };

function getCarrierDefaults(code: string) {
  return CARRIER_DEFAULTS[code.toLowerCase()] ?? FALLBACK_DEFAULTS;
}

const inp: React.CSSProperties = {
  border: "1px solid #e5e7eb",
  borderRadius: 8,
  padding: "8px 12px",
  fontSize: 13,
  width: "100%",
  boxSizing: "border-box",
  fontFamily: "inherit",
  outline: "none",
  background: "#f8fafc",
  color: "#0f172a",
};

const label: React.CSSProperties = {
  display: "block",
  fontSize: 12,
  fontWeight: 600,
  color: "#64748b",
  marginBottom: 6,
  textTransform: "uppercase",
  letterSpacing: "0.04em",
};

export default function CarrierAPIPage() {
  const params = useParams();
  const carrierId = Number(params.id);

  const [carrier, setCarrier] = useState<AdminCarrierDetail | null>(null);
  const [creds, setCreds] = useState<CarrierAPICredentials | null>(null);
  const [loading, setLoading] = useState(true);

  const [form, setForm] = useState({
    api_url: "",
    api_token: "",
    is_active: true,
    extra_config_str: "{}",
  });
  const [configError, setConfigError] = useState<string | null>(null);

  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    getAdminCarrier(carrierId)
      .then((c) => {
        setCarrier(c);
        const defaults = getCarrierDefaults(c.code);
        return getCarrierAPICredentials(c.code)
          .then((saved) => {
            setCreds(saved);
            setForm({
              api_url: saved.api_url,
              api_token: "",
              is_active: saved.is_active,
              extra_config_str: JSON.stringify(saved.extra_config ?? defaults.extra_config, null, 2),
            });
          })
          .catch(() => {
            setForm({
              api_url: defaults.api_url,
              api_token: "",
              is_active: true,
              extra_config_str: JSON.stringify(defaults.extra_config, null, 2),
            });
          });
      })
      .finally(() => setLoading(false));
  }, [carrierId]); // eslint-disable-line react-hooks/exhaustive-deps

  function validateConfig(): Record<string, unknown> | null {
    try {
      const parsed = JSON.parse(form.extra_config_str);
      setConfigError(null);
      return parsed;
    } catch {
      setConfigError("Некорректный JSON в дополнительных параметрах");
      return null;
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    const extra = validateConfig();
    if (extra === null) return;
    if (!carrier) return;

    setSaving(true);
    setSaveMsg(null);
    try {
      const saved = await upsertCarrierAPICredentials(carrier.code, {
        carrier_code: carrier.code,
        api_url: form.api_url.trim(),
        api_token: form.api_token.trim() || undefined as unknown as string,
        is_active: form.is_active,
        extra_config: extra,
      });
      setCreds(saved);
      setForm((f) => ({ ...f, api_token: "" }));
      setSaveMsg("Сохранено успешно");
    } catch (err: unknown) {
      setSaveMsg(`Ошибка: ${(err as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    if (!carrier) return;
    setTesting(true);
    setTestResult(null);
    try {
      const r = await testCarrierAPIConnection(carrier.code);
      setTestResult(r);
    } catch (err: unknown) {
      setTestResult({ ok: false, message: (err as Error).message });
    } finally {
      setTesting(false);
    }
  }

  async function handleDelete() {
    if (!carrier || !confirm("Удалить API-учётные данные? Диспетчеризация вернётся к webhook.")) return;
    setDeleting(true);
    try {
      await deleteCarrierAPICredentials(carrier.code);
      setCreds(null);
      const defaults = getCarrierDefaults(carrier.code);
      setForm({ api_url: defaults.api_url, api_token: "", is_active: true, extra_config_str: JSON.stringify(defaults.extra_config, null, 2) });
      setSaveMsg("Учётные данные удалены");
    } catch (err: unknown) {
      setSaveMsg(`Ошибка: ${(err as Error).message}`);
    } finally {
      setDeleting(false);
    }
  }

  if (loading) return <div style={{ padding: 48, textAlign: "center", color: "#64748b" }}>Загружаем…</div>;
  if (!carrier) return null;

  const dispatchBadge = creds?.is_active
    ? { label: "API-интеграция активна", bg: "#dcfce7", color: "#166534" }
    : creds
    ? { label: "API-интеграция выключена", bg: "#fef3c7", color: "#92400e" }
    : { label: "Webhook / Ручной режим", bg: "#f1f5f9", color: "#475569" };

  return (
    <>
      <div style={{ marginBottom: 20 }}>
        <span style={{ padding: "4px 12px", borderRadius: 999, fontSize: 12, fontWeight: 700, background: dispatchBadge.bg, color: dispatchBadge.color }}>
          {dispatchBadge.label}
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 20, alignItems: "start" }}>
        {/* Main form */}
        <form onSubmit={handleSave} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, padding: "24px 28px" }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", marginBottom: 20 }}>
            {creds ? "Обновить учётные данные" : "Настроить API-интеграцию"}
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={label}>API URL</label>
            <input
              style={inp}
              value={form.api_url}
              onChange={(e) => setForm((f) => ({ ...f, api_url: e.target.value }))}
              placeholder={carrier ? getCarrierDefaults(carrier.code).api_url : "https://"}
              required
            />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={label}>
              API Токен (Bearer){creds ? " — оставьте пустым, чтобы не менять" : ""}
            </label>
            <input
              style={inp}
              type="password"
              value={form.api_token}
              onChange={(e) => setForm((f) => ({ ...f, api_token: e.target.value }))}
              placeholder={creds ? `Текущий: ${creds.api_token_masked}` : "Вставьте Bearer-токен"}
              required={!creds}
              autoComplete="off"
            />
            {creds && (
              <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>
                Сохранённый токен: <span style={{ fontFamily: "monospace" }}>{creds.api_token_masked}</span>
              </div>
            )}
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={label}>Дополнительные параметры (JSON)</label>
            <textarea
              style={{ ...inp, minHeight: 130, resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
              value={form.extra_config_str}
              onChange={(e) => { setForm((f) => ({ ...f, extra_config_str: e.target.value })); setConfigError(null); }}
              spellCheck={false}
            />
            {configError && <div style={{ fontSize: 12, color: "#dc2626", marginTop: 4 }}>{configError}</div>}
            <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>
              {carrier ? getCarrierDefaults(carrier.code).hint : "Дополнительные параметры в формате JSON"}
            </div>
          </div>

          <div style={{ marginBottom: 20, display: "flex", alignItems: "center", gap: 10 }}>
            <input
              type="checkbox"
              id="is_active"
              checked={form.is_active}
              onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
              style={{ width: 16, height: 16, cursor: "pointer" }}
            />
            <label htmlFor="is_active" style={{ fontSize: 13, color: "#0f172a", cursor: "pointer", fontWeight: 500 }}>
              API-интеграция активна (если выключено — используется webhook)
            </label>
          </div>

          {saveMsg && (
            <div style={{ padding: "10px 14px", borderRadius: 8, marginBottom: 16, fontSize: 13, background: saveMsg.startsWith("Ошибка") ? "#fef2f2" : "#f0fdf4", color: saveMsg.startsWith("Ошибка") ? "#b91c1c" : "#166534" }}>
              {saveMsg}
            </div>
          )}

          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="submit"
              disabled={saving}
              style={{ padding: "10px 24px", borderRadius: 10, border: "none", background: "#0f172a", color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}
            >
              {saving ? "Сохраняем…" : creds ? "Обновить" : "Сохранить"}
            </button>
            {creds && (
              <button
                type="button"
                onClick={() => void handleDelete()}
                disabled={deleting}
                style={{ padding: "10px 16px", borderRadius: 10, border: "1px solid #fecaca", background: "#fff", color: "#dc2626", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
              >
                {deleting ? "…" : "Удалить"}
              </button>
            )}
          </div>
        </form>

        {/* Right panel: test + info */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Test connection */}
          <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, padding: "20px 22px" }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a", marginBottom: 12 }}>Проверка подключения</div>
            <p style={{ fontSize: 13, color: "#64748b", marginTop: 0, marginBottom: 14 }}>
              Отправит тестовый запрос к API перевозчика с сохранёнными учётными данными.
            </p>
            <button
              onClick={() => void handleTest()}
              disabled={testing || !creds}
              style={{ width: "100%", padding: "10px", borderRadius: 10, border: "1px solid #e5e7eb", background: creds ? "#f8fafc" : "#f1f5f9", color: creds ? "#0f172a" : "#94a3b8", fontSize: 13, fontWeight: 600, cursor: creds ? "pointer" : "not-allowed", fontFamily: "inherit" }}
            >
              {testing ? "Проверяем…" : "Проверить подключение"}
            </button>
            {testResult && (
              <div style={{ marginTop: 10, padding: "10px 12px", borderRadius: 8, fontSize: 13, background: testResult.ok ? "#f0fdf4" : "#fef2f2", color: testResult.ok ? "#166534" : "#b91c1c" }}>
                {testResult.ok ? "✓ " : "✗ "}{testResult.message}
              </div>
            )}
          </div>

          {/* How it works */}
          <div style={{ background: "#f8fafc", border: "1px solid #e5e7eb", borderRadius: 16, padding: "18px 20px" }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#0f172a", marginBottom: 10 }}>Как работает диспетчеризация</div>
            <ol style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "#475569", lineHeight: 1.7 }}>
              <li>При оплате заказа создаётся DispatchJob</li>
              <li>Если для перевозчика настроен и активен API — вызывается API напрямую</li>
              <li>Перевозчик возвращает номер накладной (и PDF, если доступен)</li>
              <li>Документ сохраняется в хранилище</li>
              <li>Если API не настроен — fallback на webhook</li>
            </ol>
          </div>

          {/* Current status */}
          {creds && (
            <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 16, padding: "18px 20px" }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#0f172a", marginBottom: 10 }}>Текущая конфигурация</div>
              <div style={{ fontSize: 12, color: "#64748b", display: "grid", gap: 6 }}>
                <div><span style={{ color: "#94a3b8" }}>URL:</span> <span style={{ fontFamily: "monospace", color: "#0f172a" }}>{creds.api_url}</span></div>
                <div><span style={{ color: "#94a3b8" }}>Токен:</span> <span style={{ fontFamily: "monospace", color: "#0f172a" }}>{creds.api_token_masked}</span></div>
                <div><span style={{ color: "#94a3b8" }}>Обновлён:</span> {new Date(creds.updated_at).toLocaleString("ru-RU")}</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
