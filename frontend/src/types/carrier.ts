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
