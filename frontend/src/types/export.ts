export interface ExportFile {
  name: string;
  path?: string;
  description: string;
  budget_version?: number | null;
  exported_at?: string;
  kind?: "report" | "dashboard";
}

export interface ExportFilesResponse {
  reports: ExportFile[];
  dashboards: ExportFile[];
}
