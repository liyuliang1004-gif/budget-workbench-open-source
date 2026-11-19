from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.services.actual_service import (
    check_actual_batch,
    delete_actual_batch,
    import_actual_batch,
    list_actual_batches,
    save_actual_upload,
    serialize_batch,
)

router = APIRouter(prefix="/api/actual", tags=["actual"])


@router.post("/upload-sales")
def upload_actual_sales(
    request: Request,
    file: UploadFile = File(...),
    year: int = Form(...),
    group_code: str | None = Form(None),
    shop_code: str | None = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    batch = save_actual_upload(file, db, request.app.state, year, "actual_sales", group_code, shop_code)
    return serialize_batch(batch)


@router.post("/upload-expense")
def upload_actual_expense(
    request: Request,
    file: UploadFile = File(...),
    year: int = Form(...),
    group_code: str | None = Form(None),
    shop_code: str | None = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    batch = save_actual_upload(file, db, request.app.state, year, "actual_expense", group_code, shop_code)
    return serialize_batch(batch)


@router.post("/check/{batch_id}")
def check_actual_file(batch_id: str, db: Session = Depends(get_db)) -> dict:
    return check_actual_batch(batch_id, db)


@router.post("/import/{batch_id}")
def import_actual_file(batch_id: str, db: Session = Depends(get_db)) -> dict:
    return import_actual_batch(batch_id, db)


@router.get("/batches")
def get_actual_batches(db: Session = Depends(get_db)) -> list[dict]:
    return list_actual_batches(db)


@router.get("/check-results/{batch_id}")
def get_actual_check_results(batch_id: str, db: Session = Depends(get_db)) -> dict:
    return check_actual_batch(batch_id, db)


@router.delete("/batches/{batch_id}")
def delete_actual_file(batch_id: str, db: Session = Depends(get_db)) -> dict:
    return delete_actual_batch(batch_id, db)
