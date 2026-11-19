from pathlib import Path

from backend.runtime_paths import data_reference, resolve_data_dir, resolve_frontend_dist_dir

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = resolve_data_dir(BASE_DIR)
USER_DATA_DIR = DATA_DIR
FRONTEND_DIST_DIR = resolve_frontend_dist_dir(BASE_DIR)

SYSTEM_NAME = "经营工作台"
PROJECT_NAME = SYSTEM_NAME
VERSION = "0.1.4"
CURRENT_STAGE = "本地可视化工作台"

DATABASE_RELATIVE_PATH = data_reference(BASE_DIR, DATA_DIR, "database/budget_system.db")
DATABASE_PATH = DATA_DIR / "database" / "budget_system.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

UPLOAD_RELATIVE_PATH = data_reference(BASE_DIR, DATA_DIR, "upload/预算表上传区")
ACTUAL_UPLOAD_RELATIVE_PATH = data_reference(BASE_DIR, DATA_DIR, "upload/实际经营表上传区")
OUTPUT_RELATIVE_PATH = data_reference(BASE_DIR, DATA_DIR, "output")
STANDARD_RELATIVE_PATH = data_reference(BASE_DIR, DATA_DIR, "standard")
CONFIG_RELATIVE_PATH = data_reference(BASE_DIR, DATA_DIR, "config")
SHOP_REGISTRY_RELATIVE_PATH = data_reference(BASE_DIR, DATA_DIR, "config/shop_registry.json")
SYSTEM_SETTINGS_RELATIVE_PATH = data_reference(BASE_DIR, DATA_DIR, "config/system_settings.json")
DASHBOARD_LAYOUT_RELATIVE_PATH = data_reference(BASE_DIR, DATA_DIR, "config/dashboard_layout.json")
SHOP_TEMPLATE_RELATIVE_PATH = "templates/店铺预算模板/店铺预算模板_V1.0.xlsx"
SUMMARY_REPORT_RELATIVE_PATH = data_reference(BASE_DIR, DATA_DIR, "output/汇总报表")
CHECK_REPORT_RELATIVE_PATH = data_reference(BASE_DIR, DATA_DIR, "output/检查报告")
STATIC_DASHBOARD_RELATIVE_PATH = data_reference(BASE_DIR, DATA_DIR, "output/静态看板")
AI_REPORT_RELATIVE_PATH = data_reference(BASE_DIR, DATA_DIR, "output/AI分析报告")
PLANNING_REPORT_RELATIVE_PATH = data_reference(BASE_DIR, DATA_DIR, "output/预算编制")
BACKUP_RELATIVE_PATH = data_reference(BASE_DIR, DATA_DIR, "backup")

AMOUNT_TOLERANCE = 0.01
QUANTITY_TOLERANCE = 0
PERCENT_TOLERANCE = 0.0001
