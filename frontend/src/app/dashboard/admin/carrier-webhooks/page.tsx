"use client";

import { useEffect, useState } from "react";
import {
  createCarrierWebhook,
  deleteCarrierWebhook,
  getCarrierWebhooks,
  testCarrierWebhook,
  updateCarrierWebhook,
} from "@/lib/api/carrier_webhooks";
import type { CarrierWebhookConfig, CarrierWebhookCreate, TestResult } from "@/types/carrier_webhooks";

const EMPTY_FORM: CarrierWebhookCreate = {
  carrier_code: "",
  push_url: "",
  webhook_secret: "",
  retry_count: 3,
  timeout_seconds: 10,
};

export default function CarrierWebhooksPage() {
  const [configs, setConfigs] = useState<CarrierWebhookConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editCode, setEditCode] = useState<string | null>(null);
  const [form, setForm] = useState<CarrierWebhookCreate>(EMPTY_FORM);
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    getCarrierWebhooks()
      .then(setConfigs)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleSubmit = async () => {
    try {
      if (editCode) {
        await updateCarrierWebhook(editCode, {
          push_url: form.push_url,
          webhook_secret: form.webhook_secret || undefined,
          retry_count: form.retry_count,
          timeout_seconds: form.timeout_seconds,
        });
      } else {
        await createCarrierWebhook(form);
      }
      setShowForm(false);
      setEditCode(null);
      setForm(EMPTY_FORM);
      load();
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  const handleEdit = (cfg: CarrierWebhookConfig) => {
    setEditCode(cfg.carrier_code);
    setForm({
      carrier_code: cfg.carrier_code,
      push_url: cfg.push_url,
      webhook_secret: "",
      retry_count: cfg.retry_count,
      timeout_seconds: cfg.timeout_seconds,
    });
    setShowForm(true);
  };

  const handleDelete = async (carrier_code: string) => {
    if (!confirm(`Удалить конфиг ${carrier_code}?`)) return;
    try {
      await deleteCarrierWebhook(carrier_code);
      load();
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  const handleTest = async (carrier_code: string) => {
    try {
      const result = await testCarrierWebhook(carrier_code);
      setTestResults((prev) => ({ ...prev, [carrier_code]: result }));
    } catch (e: unknown) {
      setTestResults((prev) => ({ ...prev, [carrier_code]: { status_code: null, response_time_ms: null, ok: false, error: (e as Error).message } }));
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>Конфиги перевозчиков</h2>
        <button
          onClick={() => { setShowForm(true); setEditCode(null); setForm(EMPTY_FORM); }}
          style={{ padding: "8px 18px", background: "#0B2545", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}
        >
          + Добавить перевозчика
        </button>
      </div>

      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "10px 16px", marginBottom: 16, color: "#991b1b" }}>
          {error}
          <button onClick={() => setError(null)} style={{ marginLeft: 12, background: "none", border: "none", cursor: "pointer", color: "#991b1b" }}>✕</button>
        </div>
      )}

      {showForm && (
        <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 12, padding: 20, marginBottom: 20 }}>
          <h3 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 600 }}>{editCode ? "Редактировать" : "Добавить"} конфиг</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {!editCode && (
              <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
                Код перевозчика
                <input value={form.carrier_code} onChange={(e) => setForm({ ...form, carrier_code: e.target.value })}
                  style={{ padding: "7px 10px", border: "1px solid #cbd5e1", borderRadius: 6, fontSize: 13 }} />
              </label>
            )}
            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
              Push URL
              <input value={form.push_url} onChange={(e) => setForm({ ...form, push_url: e.target.value })}
                style={{ padding: "7px 10px", border: "1px solid #cbd5e1", borderRadius: 6, fontSize: 13 }} />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
              Webhook Secret (необязательно)
              <input type="password" value={form.webhook_secret ?? ""} onChange={(e) => setForm({ ...form, webhook_secret: e.target.value })}
                style={{ padding: "7px 10px", border: "1px solid #cbd5e1", borderRadius: 6, fontSize: 13 }} />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
              Retry count
              <input type="number" value={form.retry_count} onChange={(e) => setForm({ ...form, retry_count: Number(e.target.value) })}
                style={{ padding: "7px 10px", border: "1px solid #cbd5e1", borderRadius: 6, fontSize: 13 }} />
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
              Timeout (сек)
              <input type="number" value={form.timeout_seconds} onChange={(e) => setForm({ ...form, timeout_seconds: Number(e.target.value) })}
                style={{ padding: "7px 10px", border: "1px solid #cbd5e1", borderRadius: 6, fontSize: 13 }} />
            </label>
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
            <button onClick={handleSubmit}
              style={{ padding: "8px 20px", background: "#0B2545", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>
              Сохранить
            </button>
            <button onClick={() => { setShowForm(false); setEditCode(null); }}
              style={{ padding: "8px 20px", background: "#e2e8f0", color: "#334155", border: "none", borderRadius: 8, cursor: "pointer" }}>
              Отмена
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div style={{ color: "#64748b", fontSize: 14 }}>Загрузка...</div>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "#f1f5f9" }}>
              <th style={th}>Перевозчик</th>
              <th style={th}>Push URL</th>
              <th style={th}>Активен</th>
              <th style={th}>Retry</th>
              <th style={th}>Timeout</th>
              <th style={th}>Тест</th>
              <th style={th}>Действия</th>
            </tr>
          </thead>
          <tbody>
            {configs.map((cfg) => (
              <tr key={cfg.carrier_code} style={{ borderBottom: "1px solid #e2e8f0" }}>
                <td style={td}><code>{cfg.carrier_code}</code></td>
                <td style={{ ...td, maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{cfg.push_url}</td>
                <td style={td}>
                  <span style={{ padding: "2px 8px", borderRadius: 99, background: cfg.is_active ? "#dcfce7" : "#fee2e2", color: cfg.is_active ? "#166534" : "#991b1b", fontSize: 12, fontWeight: 600 }}>
                    {cfg.is_active ? "Да" : "Нет"}
                  </span>
                </td>
                <td style={td}>{cfg.retry_count}</td>
                <td style={td}>{cfg.timeout_seconds}s</td>
                <td style={td}>
                  <button onClick={() => handleTest(cfg.carrier_code)}
                    style={{ padding: "4px 12px", background: "#e0f2fe", color: "#0369a1", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12 }}>
                    Тест
                  </button>
                  {testResults[cfg.carrier_code] && (
                    <span style={{ marginLeft: 8, fontSize: 12, color: testResults[cfg.carrier_code].ok ? "#166534" : "#991b1b" }}>
                      {testResults[cfg.carrier_code].ok
                        ? `${testResults[cfg.carrier_code].status_code} / ${testResults[cfg.carrier_code].response_time_ms}ms`
                        : testResults[cfg.carrier_code].error ?? "Ошибка"}
                    </span>
                  )}
                </td>
                <td style={td}>
                  <button onClick={() => handleEdit(cfg)}
                    style={{ padding: "4px 12px", background: "#f1f5f9", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12, marginRight: 6 }}>
                    Изменить
                  </button>
                  <button onClick={() => handleDelete(cfg.carrier_code)}
                    style={{ padding: "4px 12px", background: "#fee2e2", color: "#991b1b", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12 }}>
                    Удалить
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

const th: React.CSSProperties = { padding: "10px 12px", textAlign: "left", fontWeight: 600, color: "#475569", fontSize: 12 };
const td: React.CSSProperties = { padding: "10px 12px", color: "#163558" };
