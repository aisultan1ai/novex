import { apiRequest, ApiError, responseToApiError, safeFetch } from "./client";
import type {
  AdminCarrier, AdminCarrierDetail, AdminCarrierService,
  AdminCommission, AdminOrderDetail, AdminOrderRow, AdminStats,
  AdminTariffRate, AdminUser, AdminUserDetail,
  BankTransferSettings, CommissionSummary, PaginatedResponse, PlatformSettings,
} from "@/types/admin";

export { ApiError };

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") ?? "/api/v1";

const req = apiRequest;

// FormData uploads cannot use the JSON client (no Content-Type: application/json)
async function upload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const res = await safeFetch(`${BASE}${path}`, {
    method: "POST",
    credentials: "include",
    body: form,
    cache: "no-store",
  });
  if (!res.ok) throw await responseToApiError(res);
  return (await res.json().catch(() => null)) as T;
}

// ── Stats ─────────────────────────────────────────────────────────────────────
export const getAdminStats = (): Promise<AdminStats> =>
  req("/admin/users/stats");

// ── Users ─────────────────────────────────────────────────────────────────────
export const listAdminUsers = (params: { page?: number; size?: number; search?: string } = {}): Promise<PaginatedResponse<AdminUser>> => {
  const q = new URLSearchParams();
  if (params.page) q.set("page", String(params.page));
  if (params.size) q.set("size", String(params.size));
  if (params.search) q.set("search", params.search);
  return req(`/admin/users?${q}`);
};

export const getAdminUser = (id: number): Promise<AdminUserDetail> =>
  req(`/admin/users/${id}`);

export const updateAdminUser = (id: number, body: { is_active: boolean }): Promise<{ id: number; is_active: boolean }> =>
  req(`/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(body) });

export interface AdminUserCreatePayload {
  email: string;
  password: string;
  full_name?: string;
  phone?: string;
  role: "customer" | "operator" | "admin";
}

export const createAdminUser = (body: AdminUserCreatePayload): Promise<{ id: number; email: string; full_name: string | null; role: string; is_active: boolean }> =>
  req("/admin/users", { method: "POST", body: JSON.stringify(body) });

// ── Orders ────────────────────────────────────────────────────────────────────
export const listAdminOrders = (params: {
  page?: number;
  size?: number;
  status?: string;          // one status or comma-separated list
  user_id?: number;
  order_id?: number;
  orphan_waybill?: boolean;
  barcode?: string;
} = {}): Promise<PaginatedResponse<AdminOrderRow>> => {
  const q = new URLSearchParams();
  if (params.page) q.set("page", String(params.page));
  if (params.size) q.set("size", String(params.size));
  if (params.status) q.set("status", params.status);
  if (params.user_id) q.set("user_id", String(params.user_id));
  if (params.order_id) q.set("order_id", String(params.order_id));
  if (params.orphan_waybill) q.set("orphan_waybill", "true");
  if (params.barcode) q.set("barcode", params.barcode);
  return req(`/admin/orders?${q}`);
};

// Workspace counters for admin / operator (things that need a human).
export interface WorkCounters {
  payment_review: number;
  awaiting_dispatch: number;
  dispatch_failed: number;
  cancellation_pending: number;
  orphan_waybills: number;
  stuck_dispatch_jobs: number;
}

export const getWorkCounters = (): Promise<WorkCounters> => req("/admin/orders/counters");

export const getAdminOrder = (id: number): Promise<AdminOrderDetail> =>
  req(`/admin/orders/${id}`);

export interface AdminTrackingResponse {
  order_draft_id: number;
  carrier_code: string | null;
  events: { id: number; status: string; description: string | null; location: string | null; occurred_at: string }[];
}

export const getAdminOrderTracking = (id: number): Promise<AdminTrackingResponse> =>
  req(`/admin/orders/${id}/tracking`);

export const updateOrderStatus = (id: number, status: string): Promise<{ id: number; status: string }> =>
  req(`/admin/orders/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) });

// ── Carriers ──────────────────────────────────────────────────────────────────
export const listAdminCarriers = (): Promise<AdminCarrier[]> =>
  req("/admin/carriers");

export const createAdminCarrier = (body: { code: string; name: string; description?: string; is_active?: boolean; notification_email?: string | null }): Promise<AdminCarrier> =>
  req("/admin/carriers", { method: "POST", body: JSON.stringify(body) });

export const getAdminCarrier = (id: number): Promise<AdminCarrierDetail> =>
  req(`/admin/carriers/${id}`);

// notification_email: `null` - не менять; пустая строка - очистить; валидный email - задать.
export const updateAdminCarrier = (id: number, body: { name?: string; description?: string; is_active?: boolean; notification_email?: string }): Promise<AdminCarrier> =>
  req(`/admin/carriers/${id}`, { method: "PATCH", body: JSON.stringify(body) });

// Services
export const createAdminService = (carrierId: number, body: { code: string; name: string; shipment_type?: string }): Promise<AdminCarrierService> =>
  req(`/admin/carriers/${carrierId}/services`, { method: "POST", body: JSON.stringify(body) });

// Rates
export const listAdminRates = (carrierId: number, serviceId: number, page = 1, size = 50): Promise<PaginatedResponse<AdminTariffRate>> =>
  req(`/admin/carriers/${carrierId}/services/${serviceId}/rates?page=${page}&size=${size}`);

export const updateAdminRate = (
  carrierId: number,
  serviceId: number,
  rateId: number,
  body: Partial<Omit<AdminTariffRate, "id" | "is_active">>,
): Promise<AdminTariffRate> =>
  req(`/admin/carriers/${carrierId}/services/${serviceId}/rates/${rateId}`, { method: "PATCH", body: JSON.stringify(body) });

export const deleteAdminRate = (carrierId: number, serviceId: number, rateId: number): Promise<void> =>
  req(`/admin/carriers/${carrierId}/services/${serviceId}/rates/${rateId}`, { method: "DELETE" });

export const uploadTariffGrid = (carrierId: number, serviceId: number, file: File): Promise<{ inserted: number }> =>
  upload(`/admin/carriers/${carrierId}/services/${serviceId}/rates/upload`, file);

// Carrier account
export interface CarrierAccount {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

export const listCarrierAccounts = (carrierId: number): Promise<CarrierAccount[]> =>
  req(`/admin/carriers/${carrierId}/accounts`);

export const createCarrierAccount = (
  carrierId: number,
  body: { email: string; full_name?: string; temp_password: string },
): Promise<{ user_id: number; email: string; carrier_id: number }> =>
  req(`/admin/carriers/${carrierId}/account`, { method: "POST", body: JSON.stringify(body) });

// ── Commissions ────────────────────────────────────────────────────────────────
export const listAdminCommissions = (page = 1, size = 50): Promise<PaginatedResponse<AdminCommission>> =>
  req(`/admin/commissions?page=${page}&size=${size}`);

export const getCommissionsSummary = (): Promise<CommissionSummary> =>
  req("/admin/commissions/summary");

// ── Settings ───────────────────────────────────────────────────────────────────
export const getAdminSettings = (): Promise<PlatformSettings> =>
  req("/admin/settings");

export const updateAdminSettings = (body: { commission_rate?: string; bank_transfer?: Partial<BankTransferSettings> }): Promise<PlatformSettings> =>
  req("/admin/settings", { method: "PATCH", body: JSON.stringify(body) });

// ── Payments (admin) ──────────────────────────────────────────────────────────
export interface AdminPaymentItem {
  id: number;
  order_id: number;
  provider: string;
  method: string;
  status: string;
  amount: number;
  currency: string;
  payment_reference: string | null;
  created_at: string;
}

export interface AdminPaymentProof {
  id: number;
  file_url: string;
  file_name: string;
  file_mime_type: string;
  file_size: number | null;
  review_status: string;
  reject_reason: string | null;
  created_at: string;
}

export interface AdminPaymentDetail {
  payment: AdminPaymentItem;
  proofs: AdminPaymentProof[];
  history: { old_status: string; new_status: string; comment: string | null; created_at: string }[];
}

export const getAdminOrderPayments = (orderId: number): Promise<{ items: AdminPaymentItem[]; total: number }> =>
  req(`/admin/payments?order_id=${orderId}`);

export const getAdminPayment = (paymentId: number): Promise<AdminPaymentDetail> =>
  req(`/admin/payments/${paymentId}`);

export const approveAdminPayment = (paymentId: number): Promise<{ message: string }> =>
  req(`/admin/payments/${paymentId}/approve`, { method: "POST" });

export const rejectAdminPayment = (paymentId: number, reason: string): Promise<{ message: string }> =>
  req(`/admin/payments/${paymentId}/reject`, { method: "POST", body: JSON.stringify({ reject_reason: reason }) });

export const refundAdminPayment = (paymentId: number, reason: string): Promise<{ payment_id: number; status: string; message: string }> =>
  req(`/admin/payments/${paymentId}/refund`, { method: "POST", body: JSON.stringify({ reason }) });

// ── Carrier API credentials ────────────────────────────────────────────────

export interface CarrierAPICredentials {
  id: number;
  carrier_code: string;
  api_url: string;
  api_token_masked: string;
  is_active: boolean;
  extra_config: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface CarrierAPICredentialsPayload {
  carrier_code: string;
  api_url: string;
  api_token: string;
  is_active?: boolean;
  extra_config?: Record<string, unknown> | null;
}

export const getCarrierAPICredentials = (carrierCode: string): Promise<CarrierAPICredentials> =>
  req(`/admin/carrier-api/${carrierCode}`);

export const upsertCarrierAPICredentials = (carrierCode: string, body: CarrierAPICredentialsPayload): Promise<CarrierAPICredentials> =>
  req(`/admin/carrier-api/${carrierCode}`, { method: "POST", body: JSON.stringify(body) });

export const updateCarrierAPICredentials = (carrierCode: string, body: Partial<CarrierAPICredentialsPayload>): Promise<CarrierAPICredentials> =>
  req(`/admin/carrier-api/${carrierCode}`, { method: "PATCH", body: JSON.stringify(body) });

export const deleteCarrierAPICredentials = (carrierCode: string): Promise<void> =>
  req(`/admin/carrier-api/${carrierCode}`, { method: "DELETE" });

export const testCarrierAPIConnection = (carrierCode: string): Promise<{ ok: boolean; message: string }> =>
  req(`/admin/carrier-api/${carrierCode}/test`, { method: "POST" });

export const listSupportedCarrierAPIs = (): Promise<{ carrier_codes: string[] }> =>
  req("/admin/carrier-api/supported");

// ── Order operations ─────────────────────────────────────────────────────────

export const retryOrderDispatch = (draftId: number): Promise<{ ok: boolean; message?: string }> =>
  req(`/admin/orders/${draftId}/retry-dispatch`, { method: "POST" });

export const resolveOrphanWaybill = (orderId: number): Promise<{ id: number; orphan_waybill_number: null }> =>
  req(`/admin/orders/${orderId}/orphan-waybill/resolve`, { method: "POST" });

// ── Carrier integration settings ──────────────────────────────────────────────

export interface CarrierIntegrationConfig {
  carrier_code: string;
  push_url: string | null;
  webhook_secret_masked: string | null;
  is_active: boolean;
  retry_count: number;
  timeout_seconds: number;
  dispatch_mode: string;
  tracking_mode: string;
  last_success_at: string | null;
  last_error: string | null;
  updated_at: string | null;
}

export interface CarrierIntegrationLogItem {
  id: number;
  direction: string;
  event_type: string;
  order_id: number | null;
  http_status: number | null;
  duration_ms: number | null;
  status: string;
  error_message: string | null;
  created_at: string;
}

export const getCarrierIntegration = (carrierId: number): Promise<CarrierIntegrationConfig> =>
  req(`/admin/carriers/${carrierId}/integration`);

export const updateCarrierIntegration = (carrierId: number, body: Partial<CarrierIntegrationConfig>): Promise<CarrierIntegrationConfig> =>
  req(`/admin/carriers/${carrierId}/integration`, { method: "PUT", body: JSON.stringify(body) });

export const regenerateCarrierIntegrationSecret = (carrierId: number): Promise<{ webhook_secret: string; warning: string }> =>
  req(`/admin/carriers/${carrierId}/integration/regenerate-secret`, { method: "POST" });

export const testCarrierWebhook = (carrierId: number): Promise<{ ok: boolean; http_status?: number; duration_ms: number; response?: string; error?: string }> =>
  req(`/admin/carriers/${carrierId}/integration/test-webhook`, { method: "POST" });

export const getCarrierIntegrationLogs = (carrierId: number, limit = 50): Promise<{ items: CarrierIntegrationLogItem[]; total: number }> =>
  req(`/admin/carriers/${carrierId}/integration/logs?limit=${limit}`);

// ── Audit logs ────────────────────────────────────────────────────────────────

export interface AuditLogItem {
  id: number;
  actor_id: number | null;
  actor_email: string;
  action: string;
  resource_type: string;
  resource_id: number | null;
  old_value: string | null;
  new_value: string | null;
  created_at: string;
}

export const listAuditLogs = (params: {
  page?: number;
  size?: number;
  actor_id?: number;
  action?: string;
  resource_type?: string;
} = {}): Promise<{ items: AuditLogItem[]; total: number; page: number; size: number; pages: number }> => {
  const q = new URLSearchParams();
  if (params.page) q.set("page", String(params.page));
  if (params.size) q.set("size", String(params.size));
  if (params.actor_id) q.set("actor_id", String(params.actor_id));
  if (params.action) q.set("action", params.action);
  if (params.resource_type) q.set("resource_type", params.resource_type);
  return req(`/admin/audit-logs?${q}`);
};
