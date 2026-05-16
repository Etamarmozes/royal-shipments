from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Iterable


@dataclass
class NormalizedSalesRow:
    date: date
    store_code: str
    store_name: str | None
    item_code: str | None
    barcode: str | None
    item_name: str | None
    brand: str | None
    category: str | None
    quantity: float
    gross_sales: float
    net_sales: float
    discount_amount: float = 0.0
    return_quantity: float = 0.0


@dataclass
class NormalizedInventoryRow:
    snapshot_date: date
    store_code: str
    item_code: str | None
    barcode: str | None
    inventory_quantity: float
    available_quantity: float | None = None
    on_order_quantity: float | None = None


@dataclass
class NormalizedItem:
    item_code: str
    barcode: str | None
    item_name: str
    brand: str | None = None
    category: str | None = None
    supplier: str | None = None
    cost_price: float | None = None
    selling_price: float | None = None


@dataclass
class NormalizedStore:
    store_code: str
    store_name: str
    region: str | None = None
    store_type: str | None = None


class DataSource(ABC):
    """Phase-2 swap point. Both FileDataSource and ComaxApiDataSource implement this."""

    @abstractmethod
    def fetch_sales(self, start: date, end: date) -> Iterable[NormalizedSalesRow]: ...

    @abstractmethod
    def fetch_inventory(self, snapshot_date: date) -> Iterable[NormalizedInventoryRow]: ...

    @abstractmethod
    def fetch_items(self) -> Iterable[NormalizedItem]: ...

    @abstractmethod
    def fetch_stores(self) -> Iterable[NormalizedStore]: ...
