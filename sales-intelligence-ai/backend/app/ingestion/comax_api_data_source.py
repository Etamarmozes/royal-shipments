"""
Phase 2 placeholder. Implement when Comax API access is available.

Required env vars (already wired in config.py):
  COMAX_API_BASE_URL, COMAX_API_KEY, COMAX_API_USER, COMAX_API_PASSWORD

Then set DATA_SOURCE=comax_api in .env and the rest of the system keeps working.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable

from .data_source import (
    DataSource,
    NormalizedInventoryRow,
    NormalizedItem,
    NormalizedSalesRow,
    NormalizedStore,
)


class ComaxApiDataSource(DataSource):
    def __init__(self, base_url: str, api_key: str | None = None,
                 user: str | None = None, password: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.user = user
        self.password = password

    def fetch_sales(self, start: date, end: date) -> Iterable[NormalizedSalesRow]:
        raise NotImplementedError(
            "ComaxApiDataSource not implemented. See docs/comax_api_future_integration.md"
        )

    def fetch_inventory(self, snapshot_date: date) -> Iterable[NormalizedInventoryRow]:
        raise NotImplementedError("Phase 2")

    def fetch_items(self) -> Iterable[NormalizedItem]:
        raise NotImplementedError("Phase 2")

    def fetch_stores(self) -> Iterable[NormalizedStore]:
        raise NotImplementedError("Phase 2")
