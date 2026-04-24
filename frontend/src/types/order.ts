export type OrderDraftStatus =
  | "draft"
  | "shipment_details_completed"
  | "ready_for_checkout"
  | "awaiting_payment"
  | "paid"
  | "cancelled";

export type ShipmentPartyRole = "sender" | "recipient";

export interface CreateDraftFromQuoteRequest {
  quote_session_id: number;
}

export interface ShipmentPartyInput {
  full_name: string;
  phone: string;
  email?: string | null;
  company_name?: string | null;
  country: string;
  city: string;
  address_line1: string;
  address_line2?: string | null;
  postal_code?: string | null;
  comment?: string | null;
}

export interface ShipmentPackageInput {
  description: string;
  quantity: number;
  weight_kg: number;
  width_cm: number;
  height_cm: number;
  depth_cm: number;
  declared_value?: number | null;
  declared_value_currency?: string | null;
}

export interface UpdateShipmentDetailsRequest {
  sender: ShipmentPartyInput;
  recipient: ShipmentPartyInput;
  packages: ShipmentPackageInput[];
}

export type ShipmentPartyResponse = {
  id: number;
  role: "sender" | "recipient";
  full_name: string;
  phone: string;
  email: string | null;
  company_name: string | null;
  country: string;
  city: string;
  address_line1: string;
  address_line2: string | null;
  postal_code: string | null;
  comment: string | null;
};

export type ShipmentPackageResponse = {
  id: number;
  description: string;
  quantity: number;
  weight_kg: number;
  width_cm: number;
  height_cm: number;
  depth_cm: number;
  declared_value: number | null;
  declared_value_currency: string | null;
};

export type OrderDraftResponse = {
  draft_id: number;
  user_id: number;
  quote_session_id: number;
  selected_rate_quote_id: number;
  status: OrderDraftStatus;
  carrier_code_snapshot: string;
  carrier_name_snapshot: string;
  tariff_name_snapshot: string;
  price_snapshot: number;
  currency_snapshot: string;
  eta_days_min_snapshot: number;
  eta_days_max_snapshot: number;
  from_country_snapshot: string;
  from_city_snapshot: string;
  to_country_snapshot: string;
  to_city_snapshot: string;
  shipment_type_snapshot: string;
  created_at: string;

  sender: ShipmentPartyResponse | null;
  recipient: ShipmentPartyResponse | null;
  packages: ShipmentPackageResponse[];
};

export type OrderDraftListResponse = {
  items: OrderDraftResponse[];
  total: number;
  page: number;
  size: number;
  pages: number;
};