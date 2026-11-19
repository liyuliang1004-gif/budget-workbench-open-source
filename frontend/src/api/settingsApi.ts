import { apiGet, apiPut } from "./client";
import type { GroupShopRegistry } from "../types/upload";

export interface SettingsInfo {
  workspace: string;
  user_data_path?: string;
  database_path: string;
  upload_path: string;
  output_path: string;
  ai_enabled: boolean;
  system_name?: string;
  company_name?: string;
  default_year?: number;
  default_budget_version?: number;
  data_mode?: "formal" | "demo";
  onboarding_completed?: boolean;
  ai_config?: {
    mode: string;
    api_base: string;
    model: string;
    api_key_configured: boolean;
    api_key_masked: string;
  };
  ai_prompts?: {
    general_prompt: string;
    task_prompts: Record<string, string>;
    default_general_prompt: string;
    default_task_prompts: Record<string, string>;
    task_types: string[];
  };
  theme: string;
  [key: string]: unknown;
}

export function getSettings() {
  return apiGet<SettingsInfo>("/api/settings");
}

export function updateSettings(payload: Record<string, unknown>) {
  return apiPut<SettingsInfo>("/api/settings", payload);
}

export function getGroupsShopsForEdit() {
  return apiGet<GroupShopRegistry>("/api/metadata/groups-shops/edit");
}

export function updateGroupsShops(payload: GroupShopRegistry) {
  return apiPut<GroupShopRegistry>("/api/metadata/groups-shops", payload);
}
