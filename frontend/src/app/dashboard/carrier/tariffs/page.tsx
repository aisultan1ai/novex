"use client";

import { useCallback, useEffect, useState } from "react";

import { listCarrierRates, listCarrierServices } from "@/lib/api/carrier";
import type { CarrierServiceItem, CarrierTariffRateItem } from "@/types/carrier";

export default function CarrierTariffsPage() {
  const [services, setServices] = useState<CarrierServiceItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedService, setSelectedService] = useState<CarrierServiceItem | null>(null);
  const [rates, setRates] = useState<CarrierTariffRateItem[]>([]);
  const [ratesLoading, setRatesLoading] = useState(false);

  useEffect(() => {
    setIsLoading(true);
    listCarrierServices()
      .then((list) => {
        setServices(list);
        if (list.length > 0) setSelectedService(list[0]);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, []);

  const loadRates = useCallback((svc: CarrierServiceItem) => {
    setRatesLoading(true);
    listCarrierRates(svc.id)
      .then((res) => setRates(res.items))
      .catch((e: Error) => setError(e.message))
      .finally(() => setRatesLoading(false));
  }, []);

  useEffect(() => {
    if (selectedService) loadRates(selectedService);
  }, [selectedService, loadRates]);

  if (isLoading) return <div style={{ padding: 40, color: "#64748b" }}>Загружаем…</div>;
  if (error) {
    return (
      <div style={{ padding: "12px 16px", borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c" }}>
        {error}
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 20 }}>
      {/* Services list */}
      <div>
        <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "hidden" }}>
          <div style={{ padding: "14px 16px", borderBottom: "1px solid #e5e7eb", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: "#0f172a" }}>Услуги</span>
            <span style={{ fontSize: 11, color: "#94a3b8", padding: "2px 8px", borderRadius: 999, background: "#f1f5f9", fontWeight: 600 }}>
              Только чтение
            </span>
          </div>

          {services.length === 0 ? (
            <div style={{ padding: "24px 16px", textAlign: "center", color: "#94a3b8", fontSize: 13 }}>
              Нет услуг. Обратитесь к администратору Novex.
            </div>
          ) : (
            services.map((svc) => {
              const active = selectedService?.id === svc.id;
              return (
                <button
                  key={svc.id}
                  onClick={() => setSelectedService(svc)}
                  style={{ display: "block", width: "100%", padding: "12px 16px", textAlign: "left", border: "none", background: active ? "#f1f5f9" : "transparent", cursor: "pointer", borderBottom: "1px solid #f1f5f9", fontFamily: "inherit" }}
                >
                  <div style={{ fontSize: 14, fontWeight: active ? 700 : 500, color: "#0f172a" }}>{svc.name}</div>
                  <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>
                    {svc.code}
                    {svc.shipment_type ? ` · ${svc.shipment_type}` : ""}
                    {!svc.is_active ? " · неактивна" : ""}
                  </div>
                </button>
              );
            })
          )}
        </div>

        <div style={{ marginTop: 12, padding: "10px 14px", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, fontSize: 12, color: "#64748b", lineHeight: 1.5 }}>
          Просмотр тарифных сеток. Для изменения ставок обратитесь к администратору Novex.
        </div>
      </div>

      {/* Rates table */}
      <div>
        {!selectedService ? (
          <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, padding: 48, textAlign: "center", color: "#94a3b8", fontSize: 14 }}>
            Выберите услугу слева для просмотра тарифной сетки
          </div>
        ) : (
          <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 16, overflow: "hidden" }}>
            <div style={{ padding: "16px 20px", borderBottom: "1px solid #e5e7eb", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
              <div>
                <span style={{ fontSize: 15, fontWeight: 700, color: "#0f172a" }}>{selectedService.name}</span>
                <span style={{ fontSize: 12, color: "#94a3b8", marginLeft: 10 }}>{rates.length} строк</span>
              </div>
              <span style={{ fontFamily: "monospace", fontSize: 12, color: "#64748b", background: "#f1f5f9", padding: "4px 10px", borderRadius: 6 }}>
                {selectedService.code}
              </span>
            </div>

            {ratesLoading ? (
              <div style={{ padding: 32, textAlign: "center", color: "#64748b", fontSize: 14 }}>Загружаем…</div>
            ) : rates.length === 0 ? (
              <div style={{ padding: 32, textAlign: "center", color: "#94a3b8", fontSize: 14 }}>
                Нет ставок для этой услуги.
              </div>
            ) : (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "60px 90px 90px 100px 110px 100px 90px 90px 90px", gap: 8, padding: "10px 20px", background: "#f8fafc", borderBottom: "1px solid #e5e7eb", fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                  <span>ID</span><span>Зона</span><span>От, кг</span><span>До, кг</span><span>Базовая</span><span>Доп/ед</span><span>Ед. веса</span><span>Срок мин</span><span>Срок макс</span>
                </div>
                {rates.map((rate, idx) => (
                  <div key={rate.id} style={{ display: "grid", gridTemplateColumns: "60px 90px 90px 100px 110px 100px 90px 90px 90px", gap: 8, padding: "11px 20px", borderBottom: idx < rates.length - 1 ? "1px solid #f1f5f9" : "none", alignItems: "center", fontSize: 13 }}>
                    <span style={{ fontFamily: "monospace", color: "#94a3b8" }}>#{rate.id}</span>
                    <span style={{ fontWeight: 700, color: "#0f172a" }}>Зона {rate.zone}</span>
                    <span style={{ color: "#475569" }}>{rate.weight_from_kg}</span>
                    <span style={{ color: "#475569" }}>{rate.weight_to_kg ?? "∞"}</span>
                    <span style={{ fontWeight: 600, color: "#0f172a" }}>
                      {Number(rate.base_price).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {rate.currency}
                    </span>
                    <span style={{ color: "#64748b" }}>
                      {rate.per_unit_price != null ? Number(rate.per_unit_price).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "-"}
                    </span>
                    <span style={{ color: "#64748b" }}>
                      {rate.per_unit_weight_kg != null ? rate.per_unit_weight_kg : "-"}
                    </span>
                    <span style={{ color: "#64748b" }}>{rate.eta_days_min ?? "-"}</span>
                    <span style={{ color: "#64748b" }}>{rate.eta_days_max ?? "-"}</span>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
