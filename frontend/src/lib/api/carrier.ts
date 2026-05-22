import { apiRequest } from "./client";
import type { CarrierMeResponse, IntegrationConfig } from "@/types/carrier";

export const getCarrierMe = (): Promise<CarrierMeResponse> =>
  apiRequest("/carrier/me");

export const getIntegrationConfig = (): Promise<IntegrationConfig> =>
  apiRequest("/carrier/integration-config");
