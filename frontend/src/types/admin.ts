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

export interface AdminOrderRow {
  id: number;
  status: string;
  user_id: number;
  user_email: string | null;
  user_name: string | null;
  from_city: string;
  to_city: string;
  carrier_name: string;
  tariff_name: string;
  price: number;
  currency: string;
  created_at: string;
}

export interface AdminOrderDetail extends AdminOrderRow {
  eta_days_min: number;
  eta_days_max: number;
  shipment_type: string;
  updated_at: string;
  parties: { role: string; full_name: string; phone: string; city: string; address_line1: string }[];
  packages: { quantity: number; weight_kg: number; description: string }[];
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
}
