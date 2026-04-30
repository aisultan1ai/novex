"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import {
  createAdminService, deleteAdminRate, getAdminCarrier,
  listAdminRates, updateAdminCarrier, uploadTariffGrid,
} from "@/lib/api/admin";
import type { AdminCarrierDetail, AdminCarrierService, AdminTariffRate } from "@/types/admin";

const TEMPLATE: object[] = [
  { zone: 0, weight_from_kg: 0, weight_to_kg: 1, base_price: 1200, eta_days_min: 1, eta_days_max: 1, currency: "KZT" },
  { zone: 1, weight_from_kg: 0, weight_to_kg: 1, base_price: 1500, per_unit_price: 400, per_unit_weight_kg: 0.5, eta_days_min: 2, eta_days_max: 4, currency: "KZT" },
  { zone: 2, weight_from_kg: 0, weight_to_kg: 1, base_price: 2000, eta_days_min: 3, eta_days_max: 6, currency: "KZT" },
];

function downloadTemplate() {
  const blob = new Blob([JSON.stringify(TEMPLATE, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "tariff_template.json";
  a.click();
  URL.revokeObjectURL(url);
}

const inp: React.CSSProperties = { border: "1px solid #e5e7eb", borderRadius: 8, padding: "8px 12px", fontSize: 13, width: "100%", boxSizing: "border-box", fontFamily: "inherit", outline: "none", background: "#f8fafc", color: "#0f172a" };

export default function AdminCarrierDetailPage() {
  const params = useParams();
  const carrierId = Number(params.id);

  const [carrier, setCarrier] = useState<AdminCarrierDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedService, setSelectedService] = useState<AdminCarrierService | null>(null);
  const [rates, setRates] = useState<AdminTariffRate[]>([]);
  const [ratesLoading, setRatesLoading] = useState(false);

  const [showServiceForm, setShowServiceForm] = useState(false);
  const [serviceForm, setServiceForm] = useState({ code: "", name: "", shipment_type: "parcel" });
  const [savingSvc, setSavingSvc] = useState(false);

  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const [editingName, setEditingName] = useState(false);
  const [nameForm, setNameForm] = useState({ name: "", description: "" });
  const [savingName, setSavingName] = useState(false);

  function load() {
    setIsLoading(true);
    getAdminCarrier(carrierId)
      .then((c) => { setCarrier(c); setNameForm({ name: c.name, description: c.description ?? "" }); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }

  useEffect(() => { load(); }, [carrierId]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadRates = useCallback((svc: AdminCarrierService) => {
    setRatesLoading(true);
    listAdminRates(carrierId, svc.id)
      .then(setRates)
      .catch((e: Error) => setError(e.message))
      .finally(() => setRatesLoading(false));
  }, [carrierId]);

  useEffect(() => {
    if (selectedService) loadRates(selectedService);
  }, [selectedService, loadRates]);

  async function handleCreateService(e: React.FormEvent) {
    e.preventDefault();
    setSavingSvc(true);
    try {
      await createAdminService(carrierId, { code: serviceForm.code.trim(), name: serviceForm.name.trim(), shipment_type: serviceForm.shipment_type || undefined });
      setServiceForm({ code: "", name: "", shipment_type: "parcel" });
      setShowServiceForm(false);
      load();
    } catch (err: unknown) {
      alert((err as Error).message);
    } finally {
      setSavingSvc(false);
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !selectedService) return;
    setUploading(true);
    setUploadMsg(null);
    try {
      const res = await uploadTariffGrid(carrierId, selectedService.id, file);
      setUploadMsg(`✓ Загружено ${res.inserted} строк`);
      loadRates(selectedService);
    } catch (err: unknown) {
      setUploadMsg(`Ошибка: ${(err as Error).message}`);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function handleDeleteRate(rateId: number) {
    if (!selectedService || !confirm("Удалить строку?")) return;
    try {
      await deleteAdminRate(carrierId, selectedService.id, rateId);
      loadRates(selectedService);
    } catch (err: unknown) {
      alert((err as Error).message);
    }
  }

  async function handleSaveName(e: React.FormEvent) {
    e.preventDefault();
    setSavingName(true);
    try {
      await updateAdminCarrier(carrierId, { name: nameForm.name, description: nameForm.description || undefined });
      setEditingName(false);
      load();
    } catch (err: unknown) {
      alert((err as Error).message);
    } finally {
      setSavingName(false);
    }
  }

  if (isLoading) return <div style={{ padding: 48, textAlign: "center", color: "#64748b" }}>Загружаем…</div>;
  if (error && !carrier) return <div style={{ padding: "12px 16px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c" }}>{error}</div>;
  if (!carrier) return null;

  return (
    <>
      <div style={{ marginBottom: 20 }}>
        <Link href="/dashboard/admin/carriers" style={{ color: "#64748b", fontSize: 14, textDecoration: "none" }}>← Перевозчики</Link>
      </div>

      <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, padding: "24px 28px", marginBottom: 24 }}>
        {editingName ? (
          <form onSubmit={handleSaveName} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#64748b", marginBottom: 6 }}>Название</label>
              <input style={inp} value={nameForm.name} onChange={(e) => setNameForm((f) => ({ ...f, name: e.target.value }))} required />
            </div>
            <div>
              <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#64748b", marginBottom: 6 }}>Описание</label>
              <input style={inp} value={nameForm.description} onChange={(e) => setNameForm((f) => ({ ...f, description: e.target.value }))} />
            </div>
            <div style={{ gridColumn: "1 / -1", display: "flex", gap: 8 }}>
              <button type="submit" disabled={savingName} style={{ padding: "8px 16px", borderRadius: 8, border: "none", background: "#0f172a", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>Сохранить</button>
              <button type="button" onClick={() => setEditingName(false)} style={{ padding: "8px 16px", borderRadius: 8, border: "1px solid #e5e7eb", background: "#fff", color: "#64748b", fontSize: 13, cursor: "pointer", fontFamily: "inherit" }}>Отмена</button>
            </div>
          </form>
        ) : (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ fontSize: 22, fontWeight: 800, color: "#0f172a" }}>{carrier.name}</span>
                <span style={{ fontFamily: "monospace", fontSize: 13, color: "#94a3b8", background: "#f1f5f9", padding: "2px 8px", borderRadius: 6 }}>{carrier.code}</span>
                <span style={{ padding: "3px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, background: carrier.is_active ? "#dcfce7" : "#f1f5f9", color: carrier.is_active ? "#166534" : "#94a3b8" }}>
                  {carrier.is_active ? "Активен" : "Неактивен"}
                </span>
              </div>
              {carrier.description && <div style={{ fontSize: 13, color: "#64748b", marginTop: 6 }}>{carrier.description}</div>}
            </div>
            <button onClick={() => setEditingName(true)} style={{ padding: "8px 16px", borderRadius: 10, border: "1px solid #e5e7eb", background: "#fff", color: "#0f172a", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
              Редактировать
            </button>
          </div>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 20 }}>
        <div>
          <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "hidden" }}>
            <div style={{ padding: "14px 16px", borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>Тарифы</span>
              <button onClick={() => setShowServiceForm((v) => !v)} style={{ fontSize: 20, lineHeight: 1, background: "none", border: "none", cursor: "pointer", color: "#64748b", padding: 0, fontFamily: "inherit" }}>+</button>
            </div>

            {showServiceForm && (
              <form onSubmit={handleCreateService} style={{ padding: "12px 16px", borderBottom: "1px solid #f1f5f9", background: "#f8fafc" }}>
                <input style={{ ...inp, marginBottom: 8 }} value={serviceForm.code} onChange={(e) => setServiceForm((f) => ({ ...f, code: e.target.value }))} placeholder="Код (standard)" required pattern="[a-z0-9_-]+" />
                <input style={{ ...inp, marginBottom: 8 }} value={serviceForm.name} onChange={(e) => setServiceForm((f) => ({ ...f, name: e.target.value }))} placeholder="Название" required />
                <select style={{ ...inp, marginBottom: 8 }} value={serviceForm.shipment_type} onChange={(e) => setServiceForm((f) => ({ ...f, shipment_type: e.target.value }))}>
                  <option value="parcel">Посылка</option>
                  <option value="document">Документ</option>
                  <option value="cargo">Груз</option>
                </select>
                <button type="submit" disabled={savingSvc} style={{ width: "100%", padding: "8px", borderRadius: 8, border: "none", background: "#0f172a", color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
                  {savingSvc ? "..." : "Добавить"}
                </button>
              </form>
            )}

            {carrier.services.length === 0 ? (
              <div style={{ padding: "24px 16px", textAlign: "center", color: "#94a3b8", fontSize: 13 }}>Нет тарифов</div>
            ) : (
              carrier.services.map((svc) => {
                const active = selectedService?.id === svc.id;
                return (
                  <button
                    key={svc.id}
                    onClick={() => setSelectedService(svc)}
                    style={{ display: "block", width: "100%", padding: "12px 16px", textAlign: "left", border: "none", background: active ? "#f1f5f9" : "transparent", cursor: "pointer", borderBottom: "1px solid #f1f5f9", fontFamily: "inherit" }}
                  >
                    <div style={{ fontSize: 14, fontWeight: active ? 700 : 500, color: "#0f172a" }}>{svc.name}</div>
                    <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>{svc.code} · {svc.shipment_type}</div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        <div>
          {!selectedService ? (
            <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, padding: 48, textAlign: "center", color: "#94a3b8", fontSize: 14 }}>
              Выберите тариф слева для просмотра/редактирования ставок
            </div>
          ) : (
            <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "hidden" }}>
              <div style={{ padding: "16px 20px", borderBottom: "1px solid #e5e7eb", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
                <div>
                  <span style={{ fontSize: 15, fontWeight: 700, color: "#0f172a" }}>{selectedService.name}</span>
                  <span style={{ fontSize: 12, color: "#94a3b8", marginLeft: 10 }}>{rates.length} строк</span>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button onClick={downloadTemplate} style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #e5e7eb", background: "#fff", color: "#0f172a", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
                    📥 Шаблон JSON
                  </button>
                  <label style={{ padding: "8px 14px", borderRadius: 8, border: "none", background: "#0f172a", color: "#ffffff", fontSize: 12, fontWeight: 600, cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6 }}>
                    {uploading ? "Загружаем..." : "📤 Загрузить JSON"}
                    <input ref={fileRef} type="file" accept=".json" style={{ display: "none" }} onChange={handleUpload} disabled={uploading} />
                  </label>
                </div>
              </div>

              {uploadMsg && (
                <div style={{ padding: "10px 20px", fontSize: 13, background: uploadMsg.startsWith("✓") ? "#f0fdf4" : "#fef2f2", color: uploadMsg.startsWith("✓") ? "#166534" : "#b91c1c", borderBottom: "1px solid #e5e7eb" }}>
                  {uploadMsg}
                </div>
              )}

              {ratesLoading ? (
                <div style={{ padding: 32, textAlign: "center", color: "#64748b", fontSize: 14 }}>Загружаем…</div>
              ) : rates.length === 0 ? (
                <div style={{ padding: 32, textAlign: "center", color: "#94a3b8", fontSize: 14 }}>
                  Нет ставок. Загрузите JSON-файл для импорта.
                </div>
              ) : (
                <>
                  <div style={{ display: "grid", gridTemplateColumns: "50px 80px 80px 100px 80px 80px 80px 80px 40px", gap: 8, padding: "10px 20px", background: "#f8fafc", borderBottom: "1px solid #e5e7eb", fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                    <span>ID</span>
                    <span>Зона</span>
                    <span>От, кг</span>
                    <span>До, кг</span>
                    <span>Базовая</span>
                    <span>Доп/ед</span>
                    <span>Срок мин</span>
                    <span>Срок макс</span>
                    <span></span>
                  </div>
                  {rates.map((rate, idx) => (
                    <div key={rate.id} style={{ display: "grid", gridTemplateColumns: "50px 80px 80px 100px 80px 80px 80px 80px 40px", gap: 8, padding: "11px 20px", borderBottom: idx < rates.length - 1 ? "1px solid #f1f5f9" : "none", alignItems: "center", fontSize: 13 }}>
                      <span style={{ fontFamily: "monospace", color: "#94a3b8" }}>#{rate.id}</span>
                      <span style={{ fontWeight: 700, color: "#0f172a" }}>Зона {rate.zone}</span>
                      <span style={{ color: "#475569" }}>{rate.weight_from_kg}</span>
                      <span style={{ color: "#475569" }}>{rate.weight_to_kg ?? "∞"}</span>
                      <span style={{ fontWeight: 600, color: "#0f172a" }}>{Number(rate.base_price).toLocaleString("ru-RU")}</span>
                      <span style={{ color: "#64748b" }}>{rate.per_unit_price ? Number(rate.per_unit_price).toLocaleString("ru-RU") : "—"}</span>
                      <span style={{ color: "#64748b" }}>{rate.eta_days_min ?? "—"}</span>
                      <span style={{ color: "#64748b" }}>{rate.eta_days_max ?? "—"}</span>
                      <button onClick={() => void handleDeleteRate(rate.id)} style={{ width: 28, height: 28, borderRadius: 6, border: "1px solid #fecaca", background: "#fff", color: "#ef4444", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, padding: 0 }}>
                        ×
                      </button>
                    </div>
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
