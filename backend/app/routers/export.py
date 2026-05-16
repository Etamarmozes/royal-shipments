from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO

from ..database import get_db
from ..services import export_service

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/excel")
def export_excel(db: Session = Depends(get_db)):
    data = export_service.build_workbook(db)
    fname = f"royal_linen_shipments_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
