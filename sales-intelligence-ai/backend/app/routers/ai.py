from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import analytics
from ..ai import answer_question
from ..database import get_db
from ..schemas.common import ChatRequest, ChatResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    out = answer_question(db, req.question)
    return ChatResponse(**out)


@router.post("/ceo-summary")
def ceo_summary(date_range: str = "this_month", db: Session = Depends(get_db)) -> dict:
    return analytics.generate_ceo_summary(db, date_range=date_range)


@router.post("/action-plan")
def action_plan(date_range: str = "last_30_days", max_actions: int = 10, db: Session = Depends(get_db)) -> dict:
    return analytics.generate_action_plan(db, date_range=date_range, max_actions=max_actions)
