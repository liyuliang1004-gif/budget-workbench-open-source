import json
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

from backend.config import BASE_DIR, SYSTEM_NAME, SYSTEM_SETTINGS_RELATIVE_PATH


DEFAULT_SETTINGS = {
    "system_name": SYSTEM_NAME,
    "company_name": "",
    "default_year": max(date.today().year, 2026),
    "default_budget_version": 1,
    "data_mode": "formal",
    "onboarding_completed": False,
    "theme": "dark",
    "ai_config": {
        "mode": "mock",
        "api_base": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "api_key": "",
    },
    "ai_prompts": {
        "general_prompt": "",
        "task_prompts": {},
    },
}


def get_system_settings_path(app_state=None) -> Path:
    override = getattr(app_state, "system_settings_path_override", None) if app_state else None
    path = Path(override) if override else BASE_DIR / SYSTEM_SETTINGS_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}********{value[-4:]}"


def read_system_settings(app_state=None) -> dict[str, Any]:
    path = get_system_settings_path(app_state)
    if not path.exists():
        return deepcopy(DEFAULT_SETTINGS)
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return deepcopy(DEFAULT_SETTINGS)
    settings = deepcopy(DEFAULT_SETTINGS)
    settings.update({key: value for key, value in stored.items() if key not in {"ai_config", "ai_prompts"}})
    if settings.get("system_name") == "预算工作台":
        settings["system_name"] = SYSTEM_NAME
    ai_config = deepcopy(DEFAULT_SETTINGS["ai_config"])
    ai_config.update(stored.get("ai_config") or {})
    settings["ai_config"] = ai_config
    ai_prompts = deepcopy(DEFAULT_SETTINGS["ai_prompts"])
    stored_prompts = stored.get("ai_prompts") if isinstance(stored.get("ai_prompts"), dict) else {}
    ai_prompts["general_prompt"] = str(stored_prompts.get("general_prompt") or "")
    task_prompts = stored_prompts.get("task_prompts") if isinstance(stored_prompts.get("task_prompts"), dict) else {}
    ai_prompts["task_prompts"] = {str(key): str(value or "") for key, value in task_prompts.items()}
    settings["ai_prompts"] = ai_prompts
    return settings


def write_system_settings(payload: dict[str, Any], app_state=None) -> dict[str, Any]:
    current = read_system_settings(app_state)
    if "system_name" in payload:
        current["system_name"] = str(payload["system_name"]).strip() or SYSTEM_NAME
    if "company_name" in payload:
        current["company_name"] = str(payload["company_name"] or "").strip()
    if "default_year" in payload:
        try:
            current["default_year"] = max(2000, int(payload["default_year"]))
        except (TypeError, ValueError):
            current["default_year"] = DEFAULT_SETTINGS["default_year"]
    if "default_budget_version" in payload:
        try:
            current["default_budget_version"] = max(1, int(payload["default_budget_version"]))
        except (TypeError, ValueError):
            current["default_budget_version"] = 1
    if "data_mode" in payload:
        current["data_mode"] = "demo" if payload["data_mode"] == "demo" else "formal"
    if "onboarding_completed" in payload:
        current["onboarding_completed"] = bool(payload["onboarding_completed"])
    if "theme" in payload:
        current["theme"] = "dark" if payload["theme"] == "dark" else "light"
    if "ai_config" in payload and isinstance(payload["ai_config"], dict):
        ai_config = current["ai_config"].copy()
        for key in ["mode", "api_base", "model", "api_key"]:
            if key in payload["ai_config"]:
                next_value = str(payload["ai_config"][key] or "").strip()
                if key == "api_key" and not next_value:
                    continue
                ai_config[key] = next_value
        current["ai_config"] = ai_config
    if "ai_prompts" in payload and isinstance(payload["ai_prompts"], dict):
        ai_prompts = deepcopy(current.get("ai_prompts") or DEFAULT_SETTINGS["ai_prompts"])
        if "general_prompt" in payload["ai_prompts"]:
            ai_prompts["general_prompt"] = str(payload["ai_prompts"]["general_prompt"] or "").strip()
        if isinstance(payload["ai_prompts"].get("task_prompts"), dict):
            task_prompts = dict(ai_prompts.get("task_prompts") or {})
            for key, value in payload["ai_prompts"]["task_prompts"].items():
                task_prompts[str(key)] = str(value or "").strip()
            ai_prompts["task_prompts"] = task_prompts
        current["ai_prompts"] = ai_prompts
    get_system_settings_path(app_state).write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return current


def serialize_system_settings(settings: dict[str, Any]) -> dict[str, Any]:
    ai_config = settings.get("ai_config") or {}
    api_key = ai_config.get("api_key") or ""
    return {
        "system_name": settings.get("system_name") or SYSTEM_NAME,
        "company_name": str(settings.get("company_name") or ""),
        "default_year": int(settings.get("default_year") or DEFAULT_SETTINGS["default_year"]),
        "default_budget_version": int(settings.get("default_budget_version") or 1),
        "data_mode": "demo" if settings.get("data_mode") == "demo" else "formal",
        "onboarding_completed": bool(settings.get("onboarding_completed")),
        "theme": settings.get("theme") or "dark",
        "ai_enabled": bool(api_key) and ai_config.get("mode") == "deepseek",
        "ai_config": {
            "mode": ai_config.get("mode") or "mock",
            "api_base": ai_config.get("api_base") or "https://api.deepseek.com",
            "model": ai_config.get("model") or "deepseek-chat",
            "api_key_configured": bool(api_key),
            "api_key_masked": mask_secret(api_key),
        },
    }
