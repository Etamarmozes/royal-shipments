"""AI Assistant — answers questions strictly from database state.

Two modes share one endpoint, distinguished by the optional `context`:
- Management questions (no context): "what arrives this week", "what's delayed".
- Warehouse questions (context.container_id / shipment_id / page='receiving'):
  "what's supposed to be here", "how many cartons", "which docs are missing".

Context is also implicitly extracted from the question text (container number
or SHP-ID mentioned directly), and that takes precedence over the body context.
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import ai_assistant_service

router = APIRouter(prefix="/ai", tags=["ai"])


class AskContext(BaseModel):
    shipment_id: Optional[int] = None
    container_id: Optional[int] = None
    page: Optional[str] = None  # e.g. 'receiving' / 'shipment_profile' / 'container_profile'


class AskRequest(BaseModel):
    question: str
    context: Optional[AskContext] = None


@router.post("/ask")
def ask(payload: AskRequest, db: Session = Depends(get_db)):
    ctx_dict: Dict[str, Any] = {}
    if payload.context:
        if payload.context.shipment_id is not None:
            ctx_dict["shipment_id"] = payload.context.shipment_id
        if payload.context.container_id is not None:
            ctx_dict["container_id"] = payload.context.container_id
        if payload.context.page:
            ctx_dict["page"] = payload.context.page
    answer = ai_assistant_service.ask(db, payload.question, ctx_dict or None)
    return answer.to_dict()


@router.get("/suggestions")
def suggestions(
    container_id: Optional[int] = None,
    shipment_id: Optional[int] = None,
    page: Optional[str] = None,
):
    ctx: Dict[str, Any] = {}
    if container_id is not None:
        ctx["container_id"] = container_id
    if shipment_id is not None:
        ctx["shipment_id"] = shipment_id
    if page:
        ctx["page"] = page
    return {"questions": ai_assistant_service.suggestions_for(ctx or None)}
