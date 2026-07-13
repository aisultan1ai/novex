export interface CarrierInfo {
  id: number;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
}

export interface OutboundMethod {
  description: string;
  novex_calls_your_url: string | null;
  method: string;
  hmac_header: string;
  hmac_algorithm: string;
  secret_key: string | null;
  active: boolean;
}

export interface InboundMethod {
  description: string;
  your_calls_our_url: string;
  method: string;
  hmac_header: string;
  hmac_algorithm: string;
  secret_key: string | null;
}

export interface IntegrationConfig {
  carrier_code: string;
  methods: {
    outbound: OutboundMethod;
    inbound: InboundMethod;
  };
}

export interface CarrierMeResponse {
  carrier: CarrierInfo;
  integration: {
    push_url: string | null;
    webhook_secret: string | null;
    is_active: boolean;
    retry_count: number;
    timeout_seconds: number;
  };
}

export interface CarrierServiceItem {
  id: number;
  code: string;
  name: string;
  shipment_type: string | null;
  is_active: boolean;
}

export interface CarrierTariffRateItem {
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

export interface CarrierRatesResponse {
  items: CarrierTariffRateItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
}
