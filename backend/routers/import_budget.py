from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.services.import_budget_service import import_budget_file, import_checked_files

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/checked-files")
def import_all_checked_files(db: Session = Depends(get_db)) -> dict:
    return import_checked_files(db)


@router.post("/{file_id}")
def import_one_budget_file(file_id: int, force: bool = False, db: Session = Depends(get_db)) -> dict:
    return import_budget_file(file_id, db, force=force)
