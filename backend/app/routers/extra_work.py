from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.extra_work import ExtraWorkCreate, ExtraWorkUpdate, ExtraWorkRead
from ..services import extra_work_service
from ..models import ExtraWorkTask

router = APIRouter(prefix="/extra-work", tags=["extra-work"])


@router.get("", response_model=List[ExtraWorkRead])
def list_tasks(
    open_only: Optional[bool] = None,
    delayed_only: Optional[bool] = None,
    shipment_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    return extra_work_service.list_tasks(
        db, open_only=open_only, delayed_only=delayed_only, shipment_id=shipment_id
    )


@router.get("/{task_id}", response_model=ExtraWorkRead)
def get_task(task_id: int, db: Session = Depends(get_db)):
    t = db.query(ExtraWorkTask).filter(ExtraWorkTask.id == task_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    return extra_work_service.enrich_task(t, db)


@router.post("", response_model=ExtraWorkRead)
def create_task(payload: ExtraWorkCreate, db: Session = Depends(get_db)):
    t = extra_work_service.create_task(db, payload)
    return extra_work_service.enrich_task(t, db)


@router.put("/{task_id}", response_model=ExtraWorkRead)
def update_task(task_id: int, payload: ExtraWorkUpdate, db: Session = Depends(get_db)):
    t = extra_work_service.update_task(db, task_id, payload)
    return extra_work_service.enrich_task(t, db)


@router.put("/{task_id}/complete", response_model=ExtraWorkRead)
def complete_task(task_id: int, db: Session = Depends(get_db)):
    t = extra_work_service.complete_task(db, task_id)
    return extra_work_service.enrich_task(t, db)


@router.put("/{task_id}/delay", response_model=ExtraWorkRead)
def delay_task(task_id: int, payload: ExtraWorkUpdate, db: Session = Depends(get_db)):
    payload.work_status = "מתעכב"
    if not payload.delay_reason:
        raise HTTPException(status_code=400, detail="חובה להזין סיבת עיכוב")
    payload.delay_status = True
    t = extra_work_service.update_task(db, task_id, payload)
    return extra_work_service.enrich_task(t, db)
