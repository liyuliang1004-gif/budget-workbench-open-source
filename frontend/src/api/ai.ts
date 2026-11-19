import { apiDelete, apiGet, apiPost, apiPut } from "./client";

export interface AITask {
  id: number;
  task_type: string;
  scope_type: string;
  scope_value?: string | null;
  question?: string | null;
  input_data_snapshot?: string | null;
  ai_result?: string | null;
  model_name?: string | null;
  status: string;
  created_at?: string | null;
  finished_at?: string | null;
}

export function runAIAnalysis(payload: {
  task_type: string;
  scope_type: string;
  scope_value?: string;
  question?: string;
  use_mock?: boolean;
}) {
  return apiPost<{ task_id: number; status: string; model_name: string; result: string }>("/api/ai/analyze", payload);
}

export function getAITasks() {
  return apiGet<AITask[]>("/api/ai/tasks");
}

export function getAITask(taskId: number) {
  return apiGet<AITask>(`/api/ai/tasks/${taskId}`);
}

export function exportAIReport(taskId: number) {
  return apiPost<{ success: boolean; report_path: string }>(`/api/ai/export/${taskId}`);
}

export function deleteAITask(taskId: number) {
  return apiDelete<{ success: boolean; message: string }>(`/api/ai/tasks/${taskId}`);
}

export function renameAITask(taskId: number, title: string) {
  return apiPut<AITask>(`/api/ai/tasks/${taskId}/rename`, { title });
}

export function getLatestAISummary() {
  return apiGet<{ summary: string; task: AITask | null }>("/api/ai/latest-summary");
}
