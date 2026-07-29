export interface AdminStats {
  total_users: number;
  active_users: number;
  total_orders: number;
  paid_orders: number;
}

export interface AdminUser {
  id: number;
  email: string;
  full_name: string | null;
  phone: string | null;
  is_active: boolean;
  role: string | null;
  customer_type: string | null;
  company_name: string | null;
  order_count: number;
  created_at: string;
}

export interface AdminUserDetail extends AdminUser {
  billing_mode: string | null;
  orders: AdminOrderRow[];
}

export interface AdminOrderCancellation {
  reason: string;
  source: string;              // "customer_cancel" | "admin" | "system_worker" | ...
  cancelled_at: string;        // ISO
  cancelled_by_email?: string | null;
  cancelled_by_name?: string | null;
}

export interface AdminOrderRow {
  id: number;
  status: string;
  user_id: number;
  user_email: string | null;
  user_name: string | null;
  from_city: string;
  to_city: string;
  carrier_name: string;
  carrier_code: string | null;
  tariff_name: string;
  price: number;              // Customer-facing total (carrier_price + markup)
  carrier_price: number;      // What perevozchik is owed
  markup_amount: number;      // Novex profit for this order
  currency: string;
  created_at: string;
  tracking_number: string | null;
  carrier_tracking_number: string | null;
  carrier_barcode: string | null;
  cancellation?: Omit<AdminOrderCancellation, "cancelled_by_email" | "cancelled_by_name"> | null;
}

export interface AdminOrderDetail extends AdminOrderRow {
  eta_days_min: number;
  eta_days_max: number;
  shipment_type: string;
  updated_at: string;
  parties: { role: string; full_name: string; phone: string; city: string; address_line1: string }[];
  packages: { quantity: number; weight_kg: number; description: string }[];
  cancellation: AdminOrderCancellation | null;
  refund_status: "refund_pending" | "refunded" | null;
}

export interface AdminCarrier {
  id: number;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
}

export interface AdminCarrierDetail extends AdminCarrier {
  services: AdminCarrierService[];
}

export interface AdminCarrierService {
  id: number;
  code: string;
  name: string;
  shipment_type: string | null;
  is_active: boolean;
}

export interface AdminTariffRate {
  id: number;
  zone: number;
  weight_from_kg: number;
  weight_to_kg: number | null;
  base_price: number;
  per_unit_price: number | null;
  per_unit_weight_kg: number | null;
  currency: string;
  eta_days_min: number | null;
  eta_days_max: number | null;
  is_active: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages?: number;
}

export interface AdminCommission {
  id: number;
  order_draft_id: number;
  carrier_code: string;
  gross_amount: number;
  carrier_payout: number | null;
  commission_rate: number;
  commission_amount: number;
  currency: string;
  created_at: string;
  status: "active" | "reversed" | "reversal";
  reverses_commission_id: number | null;
  reversed_at: string | null;
  reversal_reason: string | null;
}

export interface CommissionSummary {
  total_gross: number;            // Turnover: what customers paid
  total_carrier_payout: number;   // What Novex owes perevozchiks
  total_commission: number;       // Novex profit / markup
  currency: string;
  count: number;
}

export interface BankTransferSettings {
  recipient_name: string;
  bank_name: string;
  iban: string;
  bin: string;
  knp: string;
}

export interface PlatformSettings {
  commission_rate: string;
  bank_transfer: BankTransferSettings;
}

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
