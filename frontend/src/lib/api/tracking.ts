import { apiRequest } from "./client";
import type { TrackingHistoryResponse } from "@/types/tracking";

export const getOrderTracking = (draftId: number): Promise<TrackingHistoryResponse> =>
  apiRequest(`/orders/${draftId}/tracking`);
