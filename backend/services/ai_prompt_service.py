from pathlib import Path
from typing import Any

from backend.config import BASE_DIR
from backend.services.system_settings_service import read_system_settings


TASK_PROMPT_FILES = {
    "部门预算分析": "部门预算分析提示词.md",
    "运营组预算分析": "运营组预算分析提示词.md",
    "店铺预算分析": "店铺预算分析提示词.md",
    "产品品类分析": "产品品类分析提示词.md",
    "费用异常分析": "费用异常分析提示词.md",
    "利润风险分析": "利润风险分析提示词.md",
    "错误检查解释": "错误检查解释提示词.md",
    "月度经营复盘": "月度经营复盘提示词.md",
    "预算平台问答": "",
}

DEFAULT_GENERAL_PROMPT = "请基于预算平台的结构化数据回答，优先说清结论、数据依据、异常原因、建议动作和需要人工确认的问题。"

DEFAULT_PLATFORM_PROMPT = (
    "你是经营工作台问答助手。你可以解释上传、检查、入库、汇总、导出、设置、版本管理和预算数据问题。"
    "你只能回答问题，不执行任何系统操作，不承诺已删除、已上传、已入库或已导出。"
)

SAFETY_PROMPT = """系统不可编辑安全规则：
- AI 只能问答，不能代替人工操作。
- 不执行上传、删除、入库、导出、清理数据、修改设置或修改数据库。
- 不承诺系统已经完成任何真实操作。
- 不得输出或推断 API Key、密钥、令牌、原始 Excel 本地路径或其他敏感信息。
- 如果用户要求执行操作，只能说明操作路径和人工确认步骤。
"""


def task_types() -> list[str]:
    return list(TASK_PROMPT_FILES.keys())


def load_default_task_prompt(task_type: str) -> str:
    prompt_file = TASK_PROMPT_FILES.get(task_type)
    if not prompt_file:
        return DEFAULT_PLATFORM_PROMPT
    path = BASE_DIR / "docs/04_AI分析规则" / prompt_file
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return "你是经营工作台问答助手。请基于结构化汇总数据和系统能力说明回答，不要编造数据。你只做问答，不做操作。"


def default_task_prompts() -> dict[str, str]:
    return {task_type: load_default_task_prompt(task_type) for task_type in task_types()}


def _user_prompt_settings(settings: dict[str, Any]) -> dict[str, Any]:
    raw = settings.get("ai_prompts") if isinstance(settings.get("ai_prompts"), dict) else {}
    raw_task_prompts = raw.get("task_prompts") if isinstance(raw.get("task_prompts"), dict) else {}
    return {
        "general_prompt": str(raw.get("general_prompt") or "").strip(),
        "task_prompts": {str(key): str(value or "").strip() for key, value in raw_task_prompts.items()},
    }


def serialize_ai_prompt_settings(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    user_prompts = _user_prompt_settings(settings or {})
    defaults = default_task_prompts()
    task_prompt_values = {}
    for task_type in task_types():
        custom_value = user_prompts["task_prompts"].get(task_type, "")
        task_prompt_values[task_type] = custom_value or defaults[task_type]
    return {
        "general_prompt": user_prompts["general_prompt"] or DEFAULT_GENERAL_PROMPT,
        "task_prompts": task_prompt_values,
        "default_general_prompt": DEFAULT_GENERAL_PROMPT,
        "default_task_prompts": defaults,
        "task_types": task_types(),
    }


def prompt_for_task(task_type: str, app_state=None) -> dict[str, str]:
    settings = read_system_settings(app_state)
    prompt_settings = serialize_ai_prompt_settings(settings)
    return {
        "safety_prompt": SAFETY_PROMPT,
        "general_prompt": prompt_settings["general_prompt"],
        "task_prompt": prompt_settings["task_prompts"].get(task_type) or load_default_task_prompt(task_type),
    }
