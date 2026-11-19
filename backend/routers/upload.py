from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.services.file_service import (
    delete_unimported_file,
    list_uploaded_files,
    save_budget_upload,
    serialize_uploaded_file,
)

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("/budget")
def upload_budget_file(
    request: Request,
    file: UploadFile = File(...),
    budget_year: int = Form(...),
    budget_version: int = Form(1),
    group_code: str = Form(...),
    shop_code: str = Form(...),
    db: Session = Depends(get_db),
) -> dict:
    uploaded_file = save_budget_upload(
        file,
        db,
        request.app.state,
        budget_version=budget_version,
        budget_year=budget_year,
        group_code=group_code,
        shop_code=shop_code,
    )
    return serialize_uploaded_file(uploaded_file)


@router.get("/files")
def get_uploaded_files(db: Session = Depends(get_db)) -> list[dict]:
    return [serialize_uploaded_file(uploaded_file) for uploaded_file in list_uploaded_files(db)]


@router.delete("/files/{file_id}")
def delete_uploaded_file(file_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    message = delete_unimported_file(file_id, db)
    return {"message": message}
