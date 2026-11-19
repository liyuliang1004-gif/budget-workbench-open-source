export interface CheckResult {
  id: number;
  file_id: number;
  check_type: string;
  severity: "error" | "warning" | "info" | string;
  error_code?: string | null;
  error_message: string;
  sheet_name?: string | null;
  cell_address?: string | null;
  row_number?: number | null;
  column_name?: string | null;
  product_code?: string | null;
  product_name?: string | null;
  month?: number | null;
  uploaded_value?: string | null;
  expected_value?: string | null;
  diff_value?: string | null;
  suggestion?: string | null;
}
