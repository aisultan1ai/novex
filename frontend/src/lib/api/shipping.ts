import { apiRequest, ApiError } from "./client";
import type {
  QuoteSelectionRequest,
  ShippingQuoteRequest,
  ShippingQuoteResponse,
} from "@/types/quote";

export { ApiError };

export async function calculateShippingQuote(
  payload: ShippingQuoteRequest,
): Promise<ShippingQuoteResponse> {
  return apiRequest<ShippingQuoteResponse>("/shipping/quote", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getShippingQuote(
  quoteSessionId: number,
  token?: string | null,
): Promise<ShippingQuoteResponse> {
  const qs = token ? `?token=${encodeURIComponent(token)}` : "";
  return apiRequest<ShippingQuoteResponse>(`/shipping/quote/${quoteSessionId}${qs}`, {
    method: "GET",
  });
}

export async function selectShippingQuote(
  quoteSessionId: number,
  payload: QuoteSelectionRequest,
  token?: string | null,
): Promise<ShippingQuoteResponse> {
  const qs = token ? `?token=${encodeURIComponent(token)}` : "";
  return apiRequest<ShippingQuoteResponse>(
    `/shipping/quote/${quoteSessionId}/select${qs}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}
