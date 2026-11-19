import subprocess
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import (
    AMOUNT_TOLERANCE,
    BASE_DIR,
    CURRENT_STAGE,
    DATABASE_RELATIVE_PATH,
    FRONTEND_DIST_DIR,
    OUTPUT_RELATIVE_PATH,
    SYSTEM_NAME,
    UPLOAD_RELATIVE_PATH,
    USER_DATA_DIR,
    VERSION,
)
from backend.database.init_db import init_database
from backend.database.db import SessionLocal
from backend.database.db import get_db
from backend.database.models import UploadCheckResult, UploadedFile
from backend.routers import actual, aggregate, ai, check, export, import_budget, metadata, planning, read_only, upload, version as version_router
from backend.read_only_mcp import create_read_only_mcp_server
from backend.services.dashboard_layout_service import (
    dashboard_widgets_data,
    read_dashboard_layout,
    reset_dashboard_layout,
    widget_catalog,
    write_dashboard_layout,
)
from backend.services.ai_prompt_service import serialize_ai_prompt_settings
from backend.services.system_settings_service import read_system_settings, serialize_system_settings, write_system_settings
from fastapi import Depends
from sqlalchemy.orm import Session

read_only_mcp = create_read_only_mcp_server(SessionLocal, lambda: app.state)
read_only_mcp_http_app = read_only_mcp.streamable_http_app(
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
    host="127.0.0.1",
)


@asynccontextmanager
async def application_lifespan(_app: FastAPI):
    init_database()
    async with read_only_mcp_http_app.router.lifespan_context(read_only_mcp_http_app):
        yield


app = FastAPI(
    title=SYSTEM_NAME,
    description="经营工作台本地 API。/api/read-only 下的接口和 /mcp 仅提供预算与实际经营数据的只读访问。",
    lifespan=application_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(upload.router)
app.include_router(actual.router)
app.include_router(check.router)
app.include_router(import_budget.router)
app.include_router(aggregate.router)
app.include_router(export.router)
app.include_router(ai.router)
app.include_router(metadata.router)
app.include_router(planning.router)
app.include_router(version_router.router)
app.include_router(read_only.router)
app.router.routes.extend(read_only_mcp_http_app.routes)

if FRONTEND_DIST_DIR.exists():
    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")


def read_git_value(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=BASE_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return "unknown"
    return result.stdout.strip() or "unknown"


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "message": "经营工作台后端运行正常",
    }


@app.get("/api/version")
def version() -> dict[str, str]:
    return {
        "system_name": SYSTEM_NAME,
        "version": VERSION,
        "stage": CURRENT_STAGE,
        "git_branch": read_git_value(["git", "branch", "--show-current"]),
        "git_commit": read_git_value(["git", "rev-parse", "--short", "HEAD"]),
    }


@app.get("/api/settings")
def settings() -> dict[str, Any]:
    raw_settings = read_system_settings(app.state)
    local_settings = serialize_system_settings(raw_settings)
    return {
        "system_name": local_settings["system_name"],
        "company_name": local_settings["company_name"],
        "default_year": local_settings["default_year"],
        "default_budget_version": local_settings["default_budget_version"],
        "data_mode": local_settings["data_mode"],
        "onboarding_completed": local_settings["onboarding_completed"],
        "workspace": str(BASE_DIR),
        "user_data_path": str(USER_DATA_DIR),
        "database_path": DATABASE_RELATIVE_PATH,
        "upload_path": UPLOAD_RELATIVE_PATH,
        "output_path": OUTPUT_RELATIVE_PATH,
        "ai_enabled": local_settings["ai_enabled"],
        "ai_config": local_settings["ai_config"],
        "ai_prompts": serialize_ai_prompt_settings(raw_settings),
        "theme": local_settings["theme"],
        "template_version": "V1.0",
        "amount_tolerance": AMOUNT_TOLERANCE,
        "format_check_enabled": True,
        "formula_check_enabled": True,
        "calculation_check_enabled": True,
    }


@app.put("/api/settings")
def update_settings(payload: dict) -> dict:
    saved = write_system_settings(payload, app.state)
    local_settings = serialize_system_settings(saved)
    return {
        "system_name": local_settings["system_name"],
        "company_name": local_settings["company_name"],
        "default_year": local_settings["default_year"],
        "default_budget_version": local_settings["default_budget_version"],
        "data_mode": local_settings["data_mode"],
        "onboarding_completed": local_settings["onboarding_completed"],
        "workspace": str(BASE_DIR),
        "user_data_path": str(USER_DATA_DIR),
        "database_path": DATABASE_RELATIVE_PATH,
        "upload_path": UPLOAD_RELATIVE_PATH,
        "output_path": OUTPUT_RELATIVE_PATH,
        "ai_enabled": local_settings["ai_enabled"],
        "ai_config": local_settings["ai_config"],
        "ai_prompts": serialize_ai_prompt_settings(saved),
        "theme": local_settings["theme"],
        "template_version": "V1.0",
        "amount_tolerance": AMOUNT_TOLERANCE,
        "format_check_enabled": True,
        "formula_check_enabled": True,
        "calculation_check_enabled": True,
    }


@app.get("/api/dashboard/layout")
def get_dashboard_layout() -> dict:
    return read_dashboard_layout(app.state)


@app.put("/api/dashboard/layout")
def update_dashboard_layout(payload: dict) -> dict:
    if payload.get("reset") is True:
        return reset_dashboard_layout(app.state)
    return write_dashboard_layout(payload, app.state)


@app.get("/api/dashboard/widget-catalog")
def get_dashboard_widget_catalog() -> dict:
    return widget_catalog()


@app.post("/api/dashboard/widgets/data")
def get_dashboard_widgets_data(payload: dict, db: Session = Depends(get_db)) -> dict:
    return dashboard_widgets_data(db, payload, app.state)


@app.get("/api/dashboard/summary")
def dashboard_summary() -> dict[str, int | str]:
    init_database()
    with SessionLocal() as db:
        uploaded_files = db.query(UploadedFile).count()
        imported_files = db.query(UploadedFile).filter(UploadedFile.import_status == "已入库").count()
        failed_checks = db.query(UploadCheckResult).filter(UploadCheckResult.severity == "error").count()
    return {
        "year": date.today().year,
        "sales_amount": 0,
        "cost_amount": 0,
        "expense_amount": 0,
        "profit_amount": 0,
        "uploaded_files": uploaded_files,
        "imported_files": imported_files,
        "error_count": failed_checks,
        "warning_count": 0,
        "message": "当前为基础占位数据，后续阶段接入真实汇总结果",
    }


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str):
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="接口不存在。")
    entry_file = "index_v2.html" if full_path == "index_v2.html" else "index.html"
    index_path = FRONTEND_DIST_DIR / entry_file
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="前端页面尚未构建，请先运行 npm run build。")
    return FileResponse(index_path)
