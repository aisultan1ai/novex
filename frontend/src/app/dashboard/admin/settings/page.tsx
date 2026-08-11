"use client";

import { useEffect, useState } from "react";
import { getAdminSettings, updateAdminSettings } from "@/lib/api/admin";
import type { BankTransferSettings } from "@/types/admin";

const EMPTY_BANK: BankTransferSettings = {
  recipient_name: "",
  bank_name: "",
  iban: "",
  bin: "",
  knp: "",
};

export default function AdminSettingsPage() {
  const [commissionRate, setCommissionRate] = useState("");
  const [bank, setBank] = useState<BankTransferSettings>(EMPTY_BANK);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  useEffect(() => {
    getAdminSettings()
      .then((s) => {
        setCommissionRate(s.commission_rate);
        setBank(s.bank_transfer ?? EMPTY_BANK);
      })
      .catch(() => setMsg({ text: "Ошибка загрузки настроек", ok: false }))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    setMsg(null);
    try {
      const updated = await updateAdminSettings({
        commission_rate: commissionRate,
        bank_transfer: bank,
      });
      setBank(updated.bank_transfer ?? EMPTY_BANK);
      setMsg({ text: "Настройки сохранены", ok: true });
    } catch (e: unknown) {
      setMsg({ text: (e as Error).message, ok: false });
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div style={{ color: "#64748b", fontSize: 14 }}>Загрузка…</div>;

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0B2545" }}>Настройки платформы</h2>
        <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>Комиссия и реквизиты для банковских переводов</p>
      </div>

      {msg && (
        <div style={{ padding: "10px 16px", borderRadius: 10, marginBottom: 20, fontSize: 14, fontWeight: 500,
          background: msg.ok ? "#f0fdf4" : "#fef2f2",
          border: `1px solid ${msg.ok ? "#bbf7d0" : "#fecaca"}`,
          color: msg.ok ? "#166534" : "#b91c1c",
        }}>
          {msg.text}
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 640 }}>

        {/* Commission */}
        <div style={s.card}>
          <h3 style={s.cardTitle}>Комиссия платформы</h3>
          <label style={s.label}>Ставка (от 0 до 1, например 0.05 = 5%)</label>
          <input
            value={commissionRate}
            onChange={(e) => setCommissionRate(e.target.value)}
            placeholder="0.0500"
            style={s.input}
          />
        </div>

        {/* Bank transfer */}
        <div style={s.card}>
          <h3 style={s.cardTitle}>Реквизиты для банковского перевода</h3>
          <p style={s.hint}>Эти данные показываются клиенту на странице оплаты заказа.</p>

          <div style={s.grid}>
            <div>
              <label style={s.label}>Получатель (название компании)</label>
              <input
                value={bank.recipient_name}
                onChange={(e) => setBank({ ...bank, recipient_name: e.target.value })}
                placeholder="ТОО Novex"
                style={s.input}
              />
            </div>
            <div>
              <label style={s.label}>Название банка</label>
              <input
                value={bank.bank_name}
                onChange={(e) => setBank({ ...bank, bank_name: e.target.value })}
                placeholder="Halyk Bank"
                style={s.input}
              />
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <label style={s.label}>IBAN</label>
              <input
                value={bank.iban}
                onChange={(e) => setBank({ ...bank, iban: e.target.value })}
                placeholder="KZ00 0000 0000 0000 0000"
                style={s.input}
              />
            </div>
            <div>
              <label style={s.label}>БИН организации</label>
              <input
                value={bank.bin}
                onChange={(e) => setBank({ ...bank, bin: e.target.value })}
                placeholder="000000000000"
                style={s.input}
              />
            </div>
            <div>
              <label style={s.label}>КНП</label>
              <input
                value={bank.knp}
                onChange={(e) => setBank({ ...bank, knp: e.target.value })}
                placeholder="710"
                style={s.input}
              />
            </div>
          </div>
        </div>

        <button onClick={handleSave} disabled={saving} style={s.btn}>
          {saving ? "Сохранение…" : "Сохранить настройки"}
        </button>
      </div>
    </>
  );
}

const s: Record<string, React.CSSProperties> = {
  card: {
    background: "#ffffff",
    border: "1px solid #E2E8EE",
    borderRadius: 16,
    padding: 24,
  },
  cardTitle: {
    margin: "0 0 16px",
    fontSize: 16,
    fontWeight: 700,
    color: "#0B2545",
  },
  hint: {
    margin: "-8px 0 16px",
    fontSize: 13,
    color: "#64748b",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 16,
  },
  label: {
    display: "block",
    fontSize: 12,
    fontWeight: 600,
    color: "#64748b",
    marginBottom: 6,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
  },
  input: {
    width: "100%",
    padding: "10px 12px",
    borderRadius: 10,
    border: "1px solid #E2E8EE",
    fontSize: 14,
    fontFamily: "inherit",
    outline: "none",
    boxSizing: "border-box",
    color: "#0B2545",
  },
  btn: {
    padding: "12px 28px",
    borderRadius: 12,
    border: "none",
    background: "#0B2545",
    color: "#ffffff",
    fontSize: 14,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
    alignSelf: "flex-start",
  },
};
