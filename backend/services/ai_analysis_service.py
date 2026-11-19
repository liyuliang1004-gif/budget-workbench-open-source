import json
import os
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from backend.config import AI_REPORT_RELATIVE_PATH, BASE_DIR
from backend.database.models import (
    AIAnalysisTask,
    DepartmentBudgetSummary,
    ExpenseBudgetDetail,
    GroupBudgetSummary,
    SalesBudgetDetail,
    ShopBudgetSummary,
    UploadCheckResult,
    UploadedFile,
)
from backend.services.system_settings_service import read_system_settings
from backend.services.ai_prompt_service import prompt_for_task

load_dotenv(BASE_DIR / ".env")

OUTPUT_STRUCTURE = """# 分析结论摘要

# 关键数据依据

# 主要异常点

# 可能原因分析

# 建议动作

# 需要人工确认的问题

# 不确定性说明
"""


def get_ai_report_dir(app_state=None) -> Path:
    override = getattr(app_state, "ai_report_dir_override", None) if app_state else None
    report_dir = Path(override) if override else BASE_DIR / AI_REPORT_RELATIVE_PATH
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def row_dict(row, fields: list[str]) -> dict:
    return {field: getattr(row, field) for field in fields}


def collect_ai_input_snapshot(db: Session, scope_type: str, scope_value: str | None) -> dict:
    upload_status = {}
    for row in db.query(UploadCheckResult).limit(200):
        key = f"{row.check_type}:{row.severity}:{row.error_code or 'UNKNOWN'}"
        upload_status[key] = upload_status.get(key, 0) + 1
    files = db.query(UploadedFile).count()
    department = [
        row_dict(row, ["year", "month", "sales_amount", "cost_amount", "expense_amount", "profit_amount", "cost_rate", "expense_rate", "profit_rate"])
        for row in db.query(DepartmentBudgetSummary).order_by(DepartmentBudgetSummary.year, DepartmentBudgetSummary.month).limit(24)
    ]
    groups = [
        row_dict(row, ["year", "month", "group_code", "sales_amount", "cost_amount", "expense_amount", "profit_amount"])
        for row in db.query(GroupBudgetSummary).order_by(GroupBudgetSummary.year, GroupBudgetSummary.month).limit(60)
    ]
    shops = [
        row_dict(row, ["year", "month", "group_code", "shop_code", "sales_amount", "cost_amount", "expense_amount", "profit_amount"])
        for row in db.query(ShopBudgetSummary).order_by(ShopBudgetSummary.year, ShopBudgetSummary.month).limit(80)
    ]
    products = {}
    for row in db.query(SalesBudgetDetail).limit(200):
        key = row.category or row.product_code
        item = products.setdefault(key, {"key": key, "quantity": 0.0, "sales_amount": 0.0, "cost_amount": 0.0, "gross_profit": 0.0})
        item["quantity"] += row.budget_quantity or 0
        item["sales_amount"] += row.budget_sales_amount or 0
        item["cost_amount"] += row.budget_cost_amount or 0
        item["gross_profit"] += row.budget_gross_profit or 0
    expenses = {}
    for row in db.query(ExpenseBudgetDetail).limit(200):
        key = row.expense_category
        expenses[key] = expenses.get(key, 0.0) + (row.budget_expense_amount or 0)
    return {
        "scope_type": scope_type,
        "scope_value": scope_value,
        "department_budget_summary": department,
        "group_budget_summary": groups,
        "shop_budget_summary": shops,
        "product_category_summary": list(products.values()),
        "expense_summary": [{"expense_category": key, "amount": value} for key, value in expenses.items()],
        "upload_check_error_summary": [{"key": key, "count": value} for key, value in upload_status.items()],
        "platform_capabilities": [
            "文件上传与格式检查",
            "公式检查与计算校验",
            "人工确认入库",
            "预算版本独立汇总",
            "报表导出与静态看板",
            "系统设置与版本管理",
            "AI 问答，不执行系统操作",
        ],
        "checked_file_count": files,
        "security_note": "AI input is built from structured summaries only. Raw Excel paths and API keys are excluded.",
    }


def build_prompt(task_type: str, question: str | None, snapshot: dict, app_state=None) -> str:
    prompts = prompt_for_task(task_type, app_state)
    return f"""{prompts["safety_prompt"]}

用户自定义通用提示词：
{prompts["general_prompt"]}

当前分析类型提示词：
{prompts["task_prompt"]}

用户问题：
{question or "请基于当前预算数据生成经营分析。"}

结构化输入数据：
{json.dumps(snapshot, ensure_ascii=False, indent=2, default=str)}

请严格使用以下输出结构：
{OUTPUT_STRUCTURE}
"""


def get_runtime_ai_config(app_state=None) -> dict:
    settings = read_system_settings(app_state)
    ai_config = settings.get("ai_config") or {}
    env_api_key = os.getenv("DEEPSEEK_API_KEY")
    return {
        "mode": ai_config.get("mode") or os.getenv("AI_ANALYSIS_MODE", "mock"),
        "api_key": ai_config.get("api_key") or env_api_key or "",
        "api_base": ai_config.get("api_base") or os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
        "model": ai_config.get("model") or os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    }


def should_use_mock(use_mock: bool | None, app_state=None) -> bool:
    if use_mock is True:
        return True
    config = get_runtime_ai_config(app_state)
    mode = str(config.get("mode") or "mock").lower()
    if mode == "mock":
        return True
    return not bool(config.get("api_key"))


def mock_result(task_type: str, scope_type: str, snapshot: dict) -> str:
    total_sales = sum(row.get("sales_amount", 0) or 0 for row in snapshot["department_budget_summary"])
    total_profit = sum(row.get("profit_amount", 0) or 0 for row in snapshot["department_budget_summary"])
    error_count = sum(item["count"] for item in snapshot["upload_check_error_summary"])
    return f"""# 分析结论摘要

当前为 mock（模拟模式）。{task_type} 已基于 {scope_type} 范围的结构化预算汇总和系统状态生成。全年预算销售额约 {total_sales:.2f}，预算利润约 {total_profit:.2f}。AI 只做问答，不执行上传、删除、入库或导出操作。

# 关键数据依据

- 部门月度汇总记录数：{len(snapshot["department_budget_summary"])}
- 运营组汇总记录数：{len(snapshot["group_budget_summary"])}
- 店铺汇总记录数：{len(snapshot["shop_budget_summary"])}
- 检查错误摘要数量：{error_count}

# 主要异常点

mock 模式不进行真实模型推理，仅提示需要关注利润率、费用率和检查错误数量。

# 可能原因分析

可能原因包括成本率偏高、费用预算集中、部分上传文件检查错误未修复。

# 建议动作

优先查看低利润月份、费用占比较高项目和 error 级别检查结果，再决定是否调整预算。

# 需要人工确认的问题

请人工确认预算模板、费用口径、成本口径和异常月份是否符合业务预期。

# 不确定性说明

这是 mock 结果，不代表 DeepSeek 真实模型分析；没有使用原始 Excel 文件，也没有读取 API Key。
"""


def call_deepseek(prompt: str, app_state=None) -> tuple[str, str]:
    config = get_runtime_ai_config(app_state)
    api_key = config["api_key"]
    api_base = config["api_base"]
    model = config["model"]
    response = requests.post(
        f"{api_base.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2},
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"], model


def run_ai_analysis(
    db: Session,
    task_type: str,
    scope_type: str,
    scope_value: str | None,
    question: str | None,
    use_mock: bool | None,
    app_state=None,
) -> AIAnalysisTask:
    snapshot = collect_ai_input_snapshot(db, scope_type, scope_value)
    snapshot_text = json.dumps(snapshot, ensure_ascii=False, default=str)
    prompt = build_prompt(task_type, question, snapshot, app_state)
    task = AIAnalysisTask(
        task_type=task_type,
        scope_type=scope_type,
        scope_value=scope_value,
        question=question,
        input_data_snapshot=snapshot_text,
        status="running",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    try:
        if should_use_mock(use_mock, app_state):
            result = mock_result(task_type, scope_type, snapshot)
            model_name = "mock"
        else:
            result, model_name = call_deepseek(prompt, app_state)
        task.ai_result = result
        task.model_name = model_name
        task.status = "success"
        task.finished_at = datetime.now()
    except Exception as exc:
        task.ai_result = f"AI 分析调用失败：{exc}"
        task.model_name = os.getenv("DEEPSEEK_MODEL", "deepseek")
        task.status = "failed"
        task.finished_at = datetime.now()
    db.commit()
    db.refresh(task)
    return task


def serialize_ai_task(task: AIAnalysisTask) -> dict:
    return {
        "id": task.id,
        "task_type": task.task_type,
        "scope_type": task.scope_type,
        "scope_value": task.scope_value,
        "question": task.question,
        "input_data_snapshot": task.input_data_snapshot,
        "ai_result": task.ai_result,
        "model_name": task.model_name,
        "status": task.status,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }


def export_ai_report(task: AIAnalysisTask, app_state=None) -> Path:
    report_dir = get_ai_report_dir(app_state)
    path = report_dir / f"AI分析报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    content = f"""# AI分析报告

任务类型：{task.task_type}

分析范围：{task.scope_type} / {task.scope_value or ""}

模型：{task.model_name or ""}

状态：{task.status}

创建时间：{task.created_at}

完成时间：{task.finished_at}

---

{task.ai_result or ""}
"""
    path.write_text(content, encoding="utf-8")
    return path
