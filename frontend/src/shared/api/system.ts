import { apiClient } from "@/shared/api/client";

export interface HealthData {
  status: string;
  service: string;
  version: string;
}

export function getHealth(signal?: AbortSignal) {
  return apiClient.request<HealthData>("/health", { signal });
}
