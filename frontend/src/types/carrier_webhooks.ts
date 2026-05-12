export interface CarrierWebhookConfig {
  id: number;
  carrier_code: string;
  push_url: string;
  is_active: boolean;
  retry_count: number;
  timeout_seconds: number;
  created_at: string;
  updated_at: string;
}

export interface CarrierWebhookCreate {
  carrier_code: string;
  push_url: string;
  webhook_secret?: string;
  retry_count?: number;
  timeout_seconds?: number;
}

export interface CarrierWebhookUpdate {
  push_url?: string;
  webhook_secret?: string;
  is_active?: boolean;
  retry_count?: number;
  timeout_seconds?: number;
}

export interface TestResult {
  status_code: number | null;
  response_time_ms: number | null;
  ok: boolean;
  error?: string;
}

export interface DispatchQueueItem {
  id: number;
  carrier_code_snapshot: string;
  carrier_name_snapshot: string;
  status: string;
  dispatch_error: string | null;
  created_at: string;
  updated_at: string;
}
