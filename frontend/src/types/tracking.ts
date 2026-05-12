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
  events: TrackingEvent[];
}
