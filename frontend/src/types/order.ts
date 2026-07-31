export type OrderDraftStatus =
  | "draft"
  | "shipment_details_completed"
  | "ready_for_checkout"
  | "awaiting_payment"
  | "payment_under_review"
  | "payment_rejected"
  | "paid"
  | "dispatch_queued"
  | "sent_to_carrier"
  | "picked_up"
  | "out_for_delivery"
  | "in_transit"
  | "arrived"
  | "delivery_failed"
  | "customs_hold"
  | "delivered"
  | "cancelled"
  | "return_requested"
  | "return_in_progress"
  | "returned"
  | "dispatch_failed"
  | "pending_manual"
  | "pending_manual_dispatch";

export type ShipmentPartyRole = "sender" | "recipient";

// Maps to CSE NameOfdeliverytype. Non-CSE carriers ignore this field (backend
// falls back to door_to_door behaviour).
export type DeliveryType =
  | "door_to_door"           // CSE: ДоставкаДоДверей
  | "warehouse_to_door"      // CSE: СкладДверь
  | "door_to_warehouse"      // CSE: Самовывоз
  | "warehouse_to_warehouse"; // CSE: СкладСклад

export interface CreateDraftFromQuoteRequest {
  quote_session_id: number;
  public_token?: string | null;
}

export interface ShipmentPartyInput {
  full_name: string;
  phone: string;
  email?: string | null;
  company_name?: string | null;
  tax_id: string;
  country: string;
  city: string;
  address_line1: string;
  address_line2?: string | null;
  postal_code?: string | null;
  comment?: string | null;
  save_to_address_book?: boolean;
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
  call_before_delivery?: boolean;
  insurance?: boolean;
  fragile?: boolean;
  delivery_type?: DeliveryType;
  sender_pvz_guid?: string | null;
  recipient_pvz_guid?: string | null;
  // Optional courier pickup - consumed by the Azimuth /order-courier flow
  // in the dispatch worker. When pickup_requested is true the backend
  // requires pickup_date + pickup_time_slot. contact_person / phone default
  // to the sender on the server side when left blank.
  pickup_requested?: boolean;
  pickup_date?: string | null;      // YYYY-MM-DD
  pickup_time_slot?: string | null; // e.g. "14:00-18:00"
  pickup_contact_person?: string | null;
  pickup_contact_phone?: string | null;
}

export type ShipmentPartyResponse = {
  id: number;
  role: "sender" | "recipient";
  full_name: string;
  phone: string;
  email: string | null;
  company_name: string | null;
  tax_id: string | null;
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

  call_before_delivery: boolean;
  insurance: boolean;
  fragile: boolean;

  delivery_type: DeliveryType;
  sender_pvz_guid: string | null;
  recipient_pvz_guid: string | null;

  pickup_requested?: boolean;
  pickup_date?: string | null;
  pickup_time_slot?: string | null;
  pickup_contact_person?: string | null;
  pickup_contact_phone?: string | null;
  // Set by the backend once /order-courier succeeded (or once, if it fails,
  // pickup_error carries the last error message for admin retry).
  pickup_scheduled?: boolean;
  pickup_error?: string | null;

  sender: ShipmentPartyResponse | null;
  recipient: ShipmentPartyResponse | null;
  packages: ShipmentPackageResponse[];

  tracking_number: string | null;

  // Заявка на отмену: pending → блок «Ожидает решения» в UI;
  // rejected → сохраняем, чтобы клиент увидел комментарий перевозчика;
  // approved / api_cancelled - обычно уже order.status === 'cancelled'.
  cancellation_request?: CancellationRequestSnippet | null;
};

export type CancellationRequestStatus = "pending" | "approved" | "api_cancelled" | "rejected";

export type CancellationRequestSnippet = {
  id: number;
  status: CancellationRequestStatus;
  reason: string;
  carrier_response: string | null;
  created_at: string;
  resolved_at: string | null;
};

export type CancelOrderResponse = {
  outcome: "cancelled" | "requested";
  order: OrderDraftResponse;
  request: CancellationRequestSnippet | null;
};

export type OrderDraftListResponse = {
  items: OrderDraftResponse[];
  total: number;
  page: number;
  size: number;
  pages: number;
};