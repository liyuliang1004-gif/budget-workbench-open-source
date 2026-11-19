import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from backend.config import BASE_DIR, SHOP_REGISTRY_RELATIVE_PATH


DEFAULT_SHOP_REGISTRY = {
    "operation_groups": [
        {
            "group_code": "G001",
            "group_name": "示例运营组",
            "status": "active",
            "shops": [
                {
                    "shop_code": "S001",
                    "shop_name": "示例店铺",
                    "status": "active",
                }
            ],
        }
    ]
}


def get_shop_registry_path(app_state=None) -> Path:
    override = getattr(app_state, "shop_registry_path_override", None) if app_state else None
    return Path(override) if override else BASE_DIR / SHOP_REGISTRY_RELATIVE_PATH


def read_shop_registry(app_state=None) -> dict[str, Any]:
    path = get_shop_registry_path(app_state)
    if not path.exists():
        return DEFAULT_SHOP_REGISTRY
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"运营组/店铺配置文件格式错误：{exc}") from exc
    groups = data.get("operation_groups")
    if not isinstance(groups, list):
        raise HTTPException(status_code=500, detail="运营组/店铺配置缺少 operation_groups 列表。")
    return data


def normalize_status(value: str | None) -> str:
    return "inactive" if value == "inactive" else "active"


def normalize_shop_registry(payload: dict[str, Any]) -> dict[str, Any]:
    groups = payload.get("operation_groups")
    if not isinstance(groups, list):
        raise HTTPException(status_code=400, detail="运营组/店铺配置必须包含 operation_groups 列表。")
    normalized_groups = []
    seen_groups = set()
    seen_shops = set()
    for group in groups:
        group_code = str(group.get("group_code") or "").strip()
        group_name = str(group.get("group_name") or "").strip()
        if not group_code or not group_name:
            raise HTTPException(status_code=400, detail="运营组编码和名称不能为空。")
        if group_code in seen_groups:
            raise HTTPException(status_code=400, detail=f"运营组编码重复：{group_code}")
        seen_groups.add(group_code)
        shops = []
        for shop in group.get("shops", []):
            shop_code = str(shop.get("shop_code") or "").strip()
            shop_name = str(shop.get("shop_name") or "").strip()
            if not shop_code or not shop_name:
                raise HTTPException(status_code=400, detail="店铺编码和名称不能为空。")
            if shop_code in seen_shops:
                raise HTTPException(status_code=400, detail=f"店铺编码重复：{shop_code}")
            seen_shops.add(shop_code)
            shops.append({"shop_code": shop_code, "shop_name": shop_name, "status": normalize_status(shop.get("status"))})
        normalized_groups.append(
            {
                "group_code": group_code,
                "group_name": group_name,
                "status": normalize_status(group.get("status")),
                "shops": shops,
            }
        )
    return {"operation_groups": normalized_groups}


def write_shop_registry(payload: dict[str, Any], app_state=None) -> dict[str, Any]:
    registry = normalize_shop_registry(payload)
    path = get_shop_registry_path(app_state)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    return list_groups_shops(app_state)


def list_groups_shops(app_state=None) -> dict[str, Any]:
    registry = read_shop_registry(app_state)
    groups = []
    for group in registry.get("operation_groups", []):
        group_code = str(group.get("group_code") or "").strip()
        group_name = str(group.get("group_name") or "").strip()
        status = normalize_status(group.get("status"))
        if status != "active":
            continue
        if not group_code or not group_name:
            continue
        shops = []
        for shop in group.get("shops", []):
            shop_code = str(shop.get("shop_code") or "").strip()
            shop_name = str(shop.get("shop_name") or "").strip()
            shop_status = normalize_status(shop.get("status"))
            if shop_status != "active":
                continue
            if shop_code and shop_name:
                shops.append({"shop_code": shop_code, "shop_name": shop_name, "group_code": group_code, "status": shop_status})
        groups.append({"group_code": group_code, "group_name": group_name, "status": status, "shops": shops})
    return {"operation_groups": groups}


def list_groups_shops_for_edit(app_state=None) -> dict[str, Any]:
    return normalize_shop_registry(read_shop_registry(app_state))


def find_group_shop(group_code: str, shop_code: str, app_state=None) -> tuple[str, str]:
    normalized_group = str(group_code or "").strip()
    normalized_shop = str(shop_code or "").strip()
    if not normalized_group or not normalized_shop:
        raise HTTPException(status_code=400, detail="上传前必须选择运营组和店铺。")
    for group in list_groups_shops(app_state)["operation_groups"]:
        if group["group_code"] != normalized_group:
            continue
        for shop in group["shops"]:
            if shop["shop_code"] == normalized_shop:
                return group["group_name"], shop["shop_name"]
    raise HTTPException(status_code=400, detail="选择的运营组和店铺不在本地配置中，请先维护配置。")
