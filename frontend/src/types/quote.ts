export type ShipmentType = "parcel" | "document";

export interface ShippingQuoteRequest {
  from_country: string;
  from_city: string;
  to_country: string;
  to_city: string;
  shipment_type: ShipmentType;
  weight_kg: number;
  quantity: number;
  width_cm: number;
  height_cm: number;
  depth_cm: number;
}

export interface RateQuoteItem {
  id: number | null;
  carrier_code: string;
  carrier_name: string;
  tariff_name: string;
  price: number;
  currency: string;
  eta_days_min: number;
  eta_days_max: number;
  badge: string | null;
  is_selected: boolean;
}

export interface ShippingQuoteResponse {
  quote_session_id: number;
  quotes: RateQuoteItem[];
}

export interface QuoteSelectionRequest {
  rate_quote_id: number;
}