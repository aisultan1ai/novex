"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import {
  createAdminService, deleteAdminRate, getAdminCarrier,
  listAdminRates, updateAdminRate, uploadTariffGrid,
} from "@/lib/api/admin";
import type { AdminCarrierService, AdminTariffRate } from "@/types/admin";

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

const inp: React.CSSProperties = {
  border: "1px solid #E2E8EE", borderRadius: 8, padding: "8px 12px",
  fontSize: 13, width: "100%", boxSizing: "border-box",
  fontFamily: "inherit", outline: "none", background: "#f8fafc", color: "#0B2545",
};

export default function AdminCarrierTariffsPage() {
  const { id } = useParams<{ id: string }>();
  const carrierId = Number(id);

  const [services, setServices] = useState<AdminCarrierService[]>([]);
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

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  function load() {
    setIsLoading(true);
    getAdminCarrier(carrierId)
      .then((c) => setServices(c.services))
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }

  useEffect(() => { load(); }, [carrierId]); // eslint-disable-line

  const loadRates = useCallback((svc: AdminCarrierService) => {
    setRatesLoading(true);
    listAdminRates(carrierId, svc.id)
      .then((res) => setRates(res.items))
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
      await createAdminService(carrierId, {
        code: serviceForm.code.trim(),
        name: serviceForm.name.trim(),
        shipment_type: serviceForm.shipment_type || undefined,
      });
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

  function startEdit(rate: AdminTariffRate) {
    setEditingId(rate.id);
    setEditDraft({
      zone: String(rate.zone),
      weight_from_kg: String(rate.weight_from_kg),
      weight_to_kg: rate.weight_to_kg != null ? String(rate.weight_to_kg) : "",
      base_price: String(rate.base_price),
      per_unit_price: rate.per_unit_price != null ? String(rate.per_unit_price) : "",
      eta_days_min: rate.eta_days_min != null ? String(rate.eta_days_min) : "",
      eta_days_max: rate.eta_days_max != null ? String(rate.eta_days_max) : "",
    });
  }

  function cancelEdit() {
    setEditingId(null);
    setEditDraft({});
  }

  async function handleSaveEdit() {
    if (!selectedService || editingId == null) return;
    setSaving(true);
    try {
      const body: Record<string, number | null> = {
        zone: Number(editDraft.zone),
        weight_from_kg: Number(editDraft.weight_from_kg),
        weight_to_kg: editDraft.weight_to_kg !== "" ? Number(editDraft.weight_to_kg) : null,
        base_price: Number(editDraft.base_price),
        per_unit_price: editDraft.per_unit_price !== "" ? Number(editDraft.per_unit_price) : null,
        eta_days_min: editDraft.eta_days_min !== "" ? Number(editDraft.eta_days_min) : null,
        eta_days_max: editDraft.eta_days_max !== "" ? Number(editDraft.eta_days_max) : null,
      };
      await updateAdminRate(carrierId, selectedService.id, editingId, body);
      setEditingId(null);
      setEditDraft({});
      loadRates(selectedService);
    } catch (err: unknown) {
      alert((err as Error).message);
    } finally {
      setSaving(false);
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

  if (isLoading) return <div style={{ padding: 40, color: "#64748b" }}>Загружаем…</div>;
  if (error) return <div style={{ padding: "12px 16px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c" }}>{error}</div>;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 20 }}>
      {/* Services list */}
      <div>
        <div style={{ background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 16, overflow: "hidden" }}>
          <div style={{ padding: "14px 16px", borderBottom: "1px solid #E2E8EE", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: "#0B2545" }}>Услуги</span>
            <button
              onClick={() => setShowServiceForm((v) => !v)}
              style={{ fontSize: 20, lineHeight: 1, background: "none", border: "none", cursor: "pointer", color: "#64748b", padding: 0, fontFamily: "inherit" }}
            >
              +
            </button>
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
              <button type="submit" disabled={savingSvc} style={{ width: "100%", padding: "8px", borderRadius: 8, border: "none", background: "#0B2545", color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
                {savingSvc ? "..." : "Добавить"}
              </button>
            </form>
          )}

          {services.length === 0 ? (
            <div style={{ padding: "24px 16px", textAlign: "center", color: "#94a3b8", fontSize: 13 }}>Нет услуг</div>
          ) : (
            services.map((svc) => {
              const active = selectedService?.id === svc.id;
              return (
                <button
                  key={svc.id}
                  onClick={() => setSelectedService(svc)}
                  style={{ display: "block", width: "100%", padding: "12px 16px", textAlign: "left", border: "none", background: active ? "#f1f5f9" : "transparent", cursor: "pointer", borderBottom: "1px solid #f1f5f9", fontFamily: "inherit" }}
                >
                  <div style={{ fontSize: 14, fontWeight: active ? 700 : 500, color: "#0B2545" }}>{svc.name}</div>
                  <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>{svc.code} · {svc.shipment_type}</div>
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* Rates table */}
      <div>
        {!selectedService ? (
          <div style={{ background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 16, padding: 48, textAlign: "center", color: "#94a3b8", fontSize: 14 }}>
            Выберите услугу слева для просмотра/редактирования ставок
          </div>
        ) : (
          <div style={{ background: "#ffffff", border: "1px solid #E2E8EE", borderRadius: 16, overflow: "hidden" }}>
            <div style={{ padding: "16px 20px", borderBottom: "1px solid #E2E8EE", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
              <div>
                <span style={{ fontSize: 15, fontWeight: 700, color: "#0B2545" }}>{selectedService.name}</span>
                <span style={{ fontSize: 12, color: "#94a3b8", marginLeft: 10 }}>{rates.length} строк</span>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={downloadTemplate} style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #E2E8EE", background: "#fff", color: "#0B2545", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
                  Шаблон JSON
                </button>
                <label style={{ padding: "8px 14px", borderRadius: 8, border: "none", background: "#0B2545", color: "#ffffff", fontSize: 12, fontWeight: 600, cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6 }}>
                  {uploading ? "Загружаем..." : "Загрузить JSON"}
                  <input ref={fileRef} type="file" accept=".json" style={{ display: "none" }} onChange={handleUpload} disabled={uploading} />
                </label>
              </div>
            </div>

            {uploadMsg && (
              <div style={{ padding: "10px 20px", fontSize: 13, background: uploadMsg.startsWith("✓") ? "#f0fdf4" : "#fef2f2", color: uploadMsg.startsWith("✓") ? "#166534" : "#b91c1c", borderBottom: "1px solid #E2E8EE" }}>
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
                <div style={{ display: "grid", gridTemplateColumns: "50px 70px 70px 90px 80px 70px 70px 70px 76px", gap: 8, padding: "10px 20px", background: "#f8fafc", borderBottom: "1px solid #E2E8EE", fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                  <span>ID</span><span>Зона</span><span>От, кг</span><span>До, кг</span><span>Базовая</span><span>Доп/ед</span><span>Срок мин</span><span>Срок макс</span><span></span>
                </div>
                {rates.map((rate, idx) => {
                  const isEditing = editingId === rate.id;
                  const cellInp: React.CSSProperties = { border: "1px solid #cbd5e1", borderRadius: 5, padding: "3px 6px", fontSize: 12, width: "100%", boxSizing: "border-box", fontFamily: "inherit", outline: "none", background: "#fff" };
                  return (
                    <div key={rate.id} style={{ display: "grid", gridTemplateColumns: "50px 70px 70px 90px 80px 70px 70px 70px 76px", gap: 8, padding: isEditing ? "8px 20px" : "11px 20px", borderBottom: idx < rates.length - 1 ? "1px solid #f1f5f9" : "none", alignItems: "center", fontSize: 13, background: isEditing ? "#f8fafc" : undefined }}>
                      <span style={{ fontFamily: "monospace", color: "#94a3b8" }}>#{rate.id}</span>
                      {isEditing ? (
                        <>
                          <input style={cellInp} value={editDraft.zone} onChange={(e) => setEditDraft((d) => ({ ...d, zone: e.target.value }))} />
                          <input style={cellInp} value={editDraft.weight_from_kg} onChange={(e) => setEditDraft((d) => ({ ...d, weight_from_kg: e.target.value }))} />
                          <input style={cellInp} value={editDraft.weight_to_kg} onChange={(e) => setEditDraft((d) => ({ ...d, weight_to_kg: e.target.value }))} placeholder="∞" />
                          <input style={cellInp} value={editDraft.base_price} onChange={(e) => setEditDraft((d) => ({ ...d, base_price: e.target.value }))} />
                          <input style={cellInp} value={editDraft.per_unit_price} onChange={(e) => setEditDraft((d) => ({ ...d, per_unit_price: e.target.value }))} placeholder="-" />
                          <input style={cellInp} value={editDraft.eta_days_min} onChange={(e) => setEditDraft((d) => ({ ...d, eta_days_min: e.target.value }))} placeholder="-" />
                          <input style={cellInp} value={editDraft.eta_days_max} onChange={(e) => setEditDraft((d) => ({ ...d, eta_days_max: e.target.value }))} placeholder="-" />
                          <div style={{ display: "flex", gap: 4 }}>
                            <button onClick={() => void handleSaveEdit()} disabled={saving} style={{ flex: 1, height: 28, borderRadius: 6, border: "1px solid #bbf7d0", background: "#f0fdf4", color: "#166534", cursor: "pointer", fontSize: 13, padding: 0 }}>✓</button>
                            <button onClick={cancelEdit} style={{ flex: 1, height: 28, borderRadius: 6, border: "1px solid #E2E8EE", background: "#fff", color: "#64748b", cursor: "pointer", fontSize: 13, padding: 0 }}>✕</button>
                          </div>
                        </>
                      ) : (
                        <>
                          <span style={{ fontWeight: 700, color: "#0B2545" }}>Зона {rate.zone}</span>
                          <span style={{ color: "#475569" }}>{rate.weight_from_kg}</span>
                          <span style={{ color: "#475569" }}>{rate.weight_to_kg ?? "∞"}</span>
                          <span style={{ fontWeight: 600, color: "#0B2545" }}>{Number(rate.base_price).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                          <span style={{ color: "#64748b" }}>{rate.per_unit_price ? Number(rate.per_unit_price).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "-"}</span>
                          <span style={{ color: "#64748b" }}>{rate.eta_days_min ?? "-"}</span>
                          <span style={{ color: "#64748b" }}>{rate.eta_days_max ?? "-"}</span>
                          <div style={{ display: "flex", gap: 4 }}>
                            <button onClick={() => startEdit(rate)} style={{ flex: 1, height: 28, borderRadius: 6, border: "1px solid #e2e8f0", background: "#fff", color: "#475569", cursor: "pointer", fontSize: 13, padding: 0 }}>✎</button>
                            <button onClick={() => void handleDeleteRate(rate.id)} style={{ flex: 1, height: 28, borderRadius: 6, border: "1px solid #fecaca", background: "#fff", color: "#ef4444", cursor: "pointer", fontSize: 14, padding: 0 }}>×</button>
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
