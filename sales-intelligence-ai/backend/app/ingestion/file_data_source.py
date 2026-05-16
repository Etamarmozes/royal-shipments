"""
Phase 1 implementation of DataSource: rows come from files in data/comax_reports/
that have already been imported into the database.

For Phase 1 this is a thin pass-through — most code reads directly from the DB
because facts are already normalized. This class exists to keep Phase 2 swap simple.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Item, Sale, Store, InventorySnapshot
from .data_source import (
    DataSource,
    NormalizedInventoryRow,
    NormalizedItem,
    NormalizedSalesRow,
    NormalizedStore,
)


class FileDataSource(DataSource):
    def __init__(self, db: Session):
        self.db = db

    def fetch_sales(self, start: date, end: date) -> Iterable[NormalizedSalesRow]:
        rows = self.db.scalars(
            select(Sale).where(Sale.date >= start, Sale.date <= end)
        ).all()
        for s in rows:
            store = self.db.get(Store, s.store_id)
            item = self.db.get(Item, s.item_id) if s.item_id else None
            yield NormalizedSalesRow(
                date=s.date,
                store_code=store.store_code if store else "",
                store_name=store.store_name if store else None,
                item_code=item.item_code if item else None,
                barcode=s.barcode,
                item_name=item.item_name if item else None,
                brand=item.brand.name if (item and item.brand) else None,
                category=item.category.name if (item and item.category) else None,
                quantity=s.quantity,
                gross_sales=s.gross_sales,
                net_sales=s.net_sales,
                discount_amount=s.discount_amount,
                return_quantity=s.return_quantity,
            )

    def fetch_inventory(self, snapshot_date: date) -> Iterable[NormalizedInventoryRow]:
        rows = self.db.scalars(
            select(InventorySnapshot).where(InventorySnapshot.snapshot_date == snapshot_date)
        ).all()
        for s in rows:
            store = self.db.get(Store, s.store_id)
            item = self.db.get(Item, s.item_id)
            yield NormalizedInventoryRow(
                snapshot_date=s.snapshot_date,
                store_code=store.store_code if store else "",
                item_code=item.item_code if item else None,
                barcode=s.barcode,
                inventory_quantity=s.inventory_quantity,
                available_quantity=s.available_quantity,
                on_order_quantity=s.on_order_quantity,
            )

    def fetch_items(self) -> Iterable[NormalizedItem]:
        for it in self.db.scalars(select(Item)).all():
            yield NormalizedItem(
                item_code=it.item_code,
                barcode=it.barcode,
                item_name=it.item_name,
                brand=it.brand.name if it.brand else None,
                category=it.category.name if it.category else None,
                supplier=it.supplier.name if it.supplier else None,
                cost_price=it.cost_price,
                selling_price=it.selling_price,
            )

    def fetch_stores(self) -> Iterable[NormalizedStore]:
        for s in self.db.scalars(select(Store)).all():
            yield NormalizedStore(
                store_code=s.store_code,
                store_name=s.store_name,
                region=s.region,
                store_type=s.store_type,
            )
