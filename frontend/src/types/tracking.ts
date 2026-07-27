export interface TrackingEvent {
  id: number;
  order_draft_id: number;
  status: string;
  description: string | null;
  location: string | null;
  carrier_status: string | null;
  occurred_at: string;
  created_at: string;
}

export interface TrackingHistoryResponse {
  order_draft_id: number;
  carrier_code: string;
  events: TrackingEvent[];
}

export interface PublicTrackingEvent {
  status: string;
  description: string | null;
  location: string | null;
  occurred_at: string;
}

export interface DeliveryInfo {
  // Public tracking: only the delivery timestamp is exposed. Recipient PII
  // (FIO, address) is intentionally omitted to prevent leaks via tracking number.
  delivered_at: string;
}

export interface PublicTrackingResponse {
  tracking_number: string;
  carrier_code: string;
  carrier_name: string;
  from_city: string;
  to_city: string;
  order_status: string;
  eta_days_min: number;
  eta_days_max: number;
  created_at: string;
  events: PublicTrackingEvent[];
  delivery: DeliveryInfo | null;
}
