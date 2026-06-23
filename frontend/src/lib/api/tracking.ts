import { apiRequest } from "./client";
import type { PublicTrackingResponse, TrackingHistoryResponse } from "@/types/tracking";

export const getOrderTracking = (draftId: number): Promise<TrackingHistoryResponse> =>
  apiRequest(`/orders/${draftId}/tracking`);

export const getPublicTracking = (trackingNumber: string): Promise<PublicTrackingResponse> =>
  apiRequest(`/tracking/${encodeURIComponent(trackingNumber)}`);
