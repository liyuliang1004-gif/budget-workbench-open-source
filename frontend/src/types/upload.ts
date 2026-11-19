export interface UploadedFileRecord {
  id: number;
  file_name: string;
  saved_file_name?: string;
  file_path: string;
  file_type: string;
  budget_year?: number | null;
  shop_code?: string | null;
  shop_name?: string | null;
  group_code?: string | null;
  group_name?: string | null;
  template_version?: string | null;
  budget_version: number;
  upload_time?: string | null;
  check_status: string;
  import_status: string;
  error_count: number;
  warning_count: number;
}

export interface ShopOption {
  shop_code: string;
  shop_name: string;
  group_code: string;
  status?: "active" | "inactive";
}

export interface OperationGroupOption {
  group_code: string;
  group_name: string;
  status?: "active" | "inactive";
  shops: ShopOption[];
}

export interface GroupShopRegistry {
  operation_groups: OperationGroupOption[];
}

export interface UploadBudgetPayload {
  file: File;
  budgetYear: number;
  budgetVersion: number;
  groupCode: string;
  shopCode: string;
}
