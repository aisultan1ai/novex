"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { getAdminSettings, updateAdminSettings } from "@/lib/api/admin";
import type { BankTransferSettings } from "@/types/admin";
import { useIsAdmin } from "@/hooks/use-is-admin";

const EMPTY_BANK: BankTransferSettings = {
  recipient_name: "",
  bank_name: "",
  iban: "",
  bin: "",
  knp: "",
  bik: "",
  kbe: "",
};

export default function AdminSettingsPage() {
  const isAdmin = useIsAdmin();
  const t = useTranslations("admin.settings");
  const [commissionRate, setCommissionRate] = useState("");
  const [bank, setBank] = useState<BankTransferSettings>(EMPTY_BANK);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  useEffect(() => {
    getAdminSettings()
      .then((s) => {
        setCommissionRate(s.commission_rate);
        setBank({ ...EMPTY_BANK, ...s.bank_transfer });
      })
      .catch(() => setMsg({ text: t("loadFailed"), ok: false }))
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
      setMsg({ text: t("saved"), ok: true });
    } catch (e: unknown) {
      setMsg({ text: (e as Error).message, ok: false });
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div style={{ color: "#64748b", fontSize: 14 }}>{t("loading")}</div>;

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#0B2545" }}>{t("title")}</h2>
        <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>{t("subtitle")}</p>
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
          <h3 style={s.cardTitle}>{t("commission")}</h3>
          <label style={s.label}>{t("rate")}</label>
          <input disabled={!isAdmin}
            value={commissionRate}
            onChange={(e) => setCommissionRate(e.target.value)}
            placeholder="0.0500"
            style={s.input}
          />
        </div>

        {/* Bank transfer */}
        <div style={s.card}>
          <h3 style={s.cardTitle}>{t("bank")}</h3>
          <p style={s.hint}>{t("bankHint")}</p>

          <div style={s.grid}>
            <div>
              <label style={s.label}>{t("recipient")}</label>
              <input disabled={!isAdmin}
                value={bank.recipient_name}
                onChange={(e) => setBank({ ...bank, recipient_name: e.target.value })}
                placeholder="ТОО Novex"
                style={s.input}
              />
            </div>
            <div>
              <label style={s.label}>{t("bankName")}</label>
              <input disabled={!isAdmin}
                value={bank.bank_name}
                onChange={(e) => setBank({ ...bank, bank_name: e.target.value })}
                placeholder="Halyk Bank"
                style={s.input}
              />
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <label style={s.label}>IBAN</label>
              <input disabled={!isAdmin}
                value={bank.iban}
                onChange={(e) => setBank({ ...bank, iban: e.target.value })}
                placeholder="KZ00 0000 0000 0000 0000"
                style={s.input}
              />
            </div>
            <div>
              <label style={s.label}>{t("bin")}</label>
              <input disabled={!isAdmin}
                value={bank.bin}
                onChange={(e) => setBank({ ...bank, bin: e.target.value })}
                placeholder="000000000000"
                style={s.input}
              />
            </div>
            <div>
              <label style={s.label}>{t("knp")}</label>
              <input disabled={!isAdmin}
                value={bank.knp}
                onChange={(e) => setBank({ ...bank, knp: e.target.value })}
                placeholder="710"
                style={s.input}
              />
            </div>
            <div>
              <label style={s.label}>{t("bik")} <span style={{ color: "#94a3b8", fontWeight: 400 }}>{t("optional")}</span></label>
              <input disabled={!isAdmin}
                value={bank.bik}
                onChange={(e) => setBank({ ...bank, bik: e.target.value })}
                placeholder="CASPKZKA"
                style={s.input}
              />
            </div>
            <div>
              <label style={s.label}>{t("kbe")} <span style={{ color: "#94a3b8", fontWeight: 400 }}>{t("optional")}</span></label>
              <input disabled={!isAdmin}
                value={bank.kbe}
                onChange={(e) => setBank({ ...bank, kbe: e.target.value })}
                placeholder="17"
                style={s.input}
              />
            </div>
          </div>
        </div>

        {isAdmin && (
          <button onClick={handleSave} disabled={saving} style={s.btn}>
            {saving ? t("saving") : t("save")}
          </button>
        )}
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
