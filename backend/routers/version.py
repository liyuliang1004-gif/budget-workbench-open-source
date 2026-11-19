from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.config import BASE_DIR
from backend.services.git_version_service import GitVersionService
from backend.services.version_backup_service import VersionBackupService


router = APIRouter(prefix="/api/version", tags=["version"])


class CreateBackupRequest(BaseModel):
    remark: str = "升级前备份"


def get_base_dir(request: Request):
    return getattr(request.app.state, "version_backup_base_dir_override", BASE_DIR)


@router.get("/status")
def get_version_status(request: Request) -> dict[str, Any]:
    return GitVersionService(get_base_dir(request)).get_status()


@router.post("/create-backup")
def create_version_backup(request: Request, payload: CreateBackupRequest | None = None) -> dict[str, Any]:
    remark = payload.remark if payload else "升级前备份"
    return VersionBackupService(get_base_dir(request)).create_backup(remark)


@router.get("/backups")
def list_version_backups(request: Request) -> list[dict[str, Any]]:
    return VersionBackupService(get_base_dir(request)).list_backups()


@router.get("/backups/{backup_id}")
def get_version_backup(request: Request, backup_id: str) -> dict[str, Any]:
    backup = VersionBackupService(get_base_dir(request)).get_backup(backup_id)
    if backup is None:
        raise HTTPException(status_code=404, detail="未找到指定备份")
    return backup
