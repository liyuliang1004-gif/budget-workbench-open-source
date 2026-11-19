from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.database.models import AIAnalysisTask
from backend.services.ai_analysis_service import export_ai_report, run_ai_analysis, serialize_ai_task

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AIAnalyzeRequest(BaseModel):
    task_type: str
    scope_type: str
    scope_value: str | None = None
    question: str | None = None
    use_mock: bool | None = None


@router.post("/analyze")
def analyze(request: Request, request_data: AIAnalyzeRequest, db: Session = Depends(get_db)) -> dict:
    task = run_ai_analysis(
        db,
        task_type=request_data.task_type,
        scope_type=request_data.scope_type,
        scope_value=request_data.scope_value,
        question=request_data.question,
        use_mock=request_data.use_mock,
        app_state=request.app.state,
    )
    return {
        "task_id": task.id,
        "status": task.status,
        "model_name": task.model_name,
        "result": task.ai_result,
    }


@router.get("/tasks")
def list_tasks(
    task_type: str | None = None,
    scope_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    query = db.query(AIAnalysisTask)
    if task_type:
        query = query.filter(AIAnalysisTask.task_type == task_type)
    if scope_type:
        query = query.filter(AIAnalysisTask.scope_type == scope_type)
    if status:
        query = query.filter(AIAnalysisTask.status == status)
    return [serialize_ai_task(task) for task in query.order_by(AIAnalysisTask.created_at.desc(), AIAnalysisTask.id.desc()).all()]


@router.put("/tasks/{task_id}/rename")
def rename_task(task_id: int, payload: dict, db: Session = Depends(get_db)) -> dict:
    title = str(payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="对话记录名称不能为空。")
    task = db.get(AIAnalysisTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="未找到 AI 分析任务。")
    task.question = title
    db.commit()
    db.refresh(task)
    return serialize_ai_task(task)


@router.get("/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    task = db.get(AIAnalysisTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="未找到 AI 分析任务。")
    return serialize_ai_task(task)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    task = db.get(AIAnalysisTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="未找到 AI 分析任务。")
    db.delete(task)
    db.commit()
    return {"success": True, "message": "AI 对话记录已删除"}


@router.post("/export/{task_id}")
def export_task(task_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    task = db.get(AIAnalysisTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="未找到 AI 分析任务。")
    path = export_ai_report(task, request.app.state)
    return {"success": True, "report_path": str(path)}


@router.get("/latest-summary")
def latest_summary(db: Session = Depends(get_db)) -> dict:
    task = db.query(AIAnalysisTask).filter(AIAnalysisTask.status == "success").order_by(AIAnalysisTask.finished_at.desc(), AIAnalysisTask.id.desc()).first()
    if task is None:
        return {"summary": "暂无 AI 分析结果", "task": None}
    first_lines = "\n".join((task.ai_result or "").splitlines()[:8])
    return {"summary": first_lines, "task": serialize_ai_task(task)}
