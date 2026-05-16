from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import (
    Brand,
    Category,
    ImportLog,
    InventorySnapshot,
    Item,
    Sale,
    Store,
)

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/status")
def status(db: Session = Depends(get_db)) -> dict:
    counts = {
        "stores": db.scalar(select(func.count(Store.id))) or 0,
        "items": db.scalar(select(func.count(Item.id))) or 0,
        "brands": db.scalar(select(func.count(Brand.id))) or 0,
        "categories": db.scalar(select(func.count(Category.id))) or 0,
        "sales_rows": db.scalar(select(func.count(Sale.id))) or 0,
        "inventory_snapshots": db.scalar(select(func.count(InventorySnapshot.id))) or 0,
        "import_logs": db.scalar(select(func.count(ImportLog.id))) or 0,
    }
    last_sales = db.scalar(select(func.max(Sale.date)))
    last_inv = db.scalar(select(func.max(InventorySnapshot.snapshot_date)))
    return {
        "counts": counts,
        "last_sales_date": last_sales.isoformat() if last_sales else None,
        "last_inventory_date": last_inv.isoformat() if last_inv else None,
        "data_source": settings.DATA_SOURCE,
        "now": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/stores")
def stores(db: Session = Depends(get_db)) -> list[dict]:
    return [
        {"id": s.id, "store_code": s.store_code, "store_name": s.store_name,
         "region": s.region, "store_type": s.store_type, "active": s.active}
        for s in db.scalars(select(Store)).all()
    ]


@router.get("/brands")
def brands(db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": b.id, "name": b.name} for b in db.scalars(select(Brand)).all()]


@router.get("/categories")
def categories(db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": c.id, "name": c.name} for c in db.scalars(select(Category)).all()]


@router.get("/items")
def items(limit: int = 100, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Item).limit(limit)).all()
    return [
        {
            "id": i.id, "item_code": i.item_code, "barcode": i.barcode,
            "item_name": i.item_name,
            "brand": i.brand.name if i.brand else None,
            "category": i.category.name if i.category else None,
            "selling_price": i.selling_price, "cost_price": i.cost_price,
        }
        for i in rows
    ]
