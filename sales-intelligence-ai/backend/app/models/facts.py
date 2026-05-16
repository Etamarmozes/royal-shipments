from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Sale(Base):
    __tablename__ = "sales"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), index=True, nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    gross_sales: Mapped[float] = mapped_column(Float, default=0.0)
    net_sales: Mapped[float] = mapped_column(Float, default=0.0)
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0)
    return_quantity: Mapped[float] = mapped_column(Float, default=0.0)
    cost_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_margin_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_logs.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_sales_date_store", "date", "store_id"),
        Index("ix_sales_date_item", "date", "item_id"),
    )


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    inventory_quantity: Mapped[float] = mapped_column(Float, default=0.0)
    available_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    on_order_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_logs.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_inv_snap_date_store_item", "snapshot_date", "store_id", "item_id"),
    )
