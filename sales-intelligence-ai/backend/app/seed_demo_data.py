"""
Seed the database with realistic synthetic data so the dashboard, AI, and report
generator have something to work with on day one.

Patterns demonstrated:
  - Keds outsells Adidas in value/outlet stores (Beit Shemesh, Ashdod, Kiryat Yam)
  - Adidas outsells Keds in flagship/general stores (Kiryat Ono, Bnei Brak, Netanya)
  - Some Adidas SKUs at low stock in flagships → fast_moving_low_stock alerts
  - Some Nautica/Lifetime SKUs are stuck → slow_moving_high_stock + stuck alerts

Run:
  python -m app.seed_demo_data
Re-running wipes the demo data and reseeds (only the demo rows; user imports stay).
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy import delete, select

from .database import init_db, session_scope
from .models import (
    Brand,
    Category,
    InventorySnapshot,
    Item,
    Sale,
    Store,
    Supplier,
)

random.seed(7)

STORES = [
    ("ST01", "Kiryat Ono", "Center", "flagship"),
    ("ST02", "Bnei Brak", "Center", "general"),
    ("ST03", "Beit Shemesh", "Jerusalem", "value"),
    ("ST04", "Netanya", "North", "general"),
    ("ST05", "Ashdod", "South", "value"),
    ("ST06", "Kiryat Yam", "North", "outlet"),
]

ITEMS = [
    # (item_code, barcode, name, brand, category, supplier, cost, price)
    ("KD-001", "7290011110011", "Keds Champion Classic White W37", "Keds", "Sneakers", "Keds Israel", 120, 249),
    ("KD-002", "7290011110028", "Keds Champion Classic Black W38", "Keds", "Sneakers", "Keds Israel", 120, 249),
    ("KD-003", "7290011110035", "Keds Triple Kick W36", "Keds", "Sneakers", "Keds Israel", 140, 279),
    ("KD-004", "7290011110042", "Keds Kickstart Canvas Navy", "Keds", "Sneakers", "Keds Israel", 110, 229),
    ("AD-001", "7290022220011", "Adidas Stan Smith White M42", "Adidas", "Sneakers", "Adidas Israel", 220, 449),
    ("AD-002", "7290022220028", "Adidas Stan Smith Green M43", "Adidas", "Sneakers", "Adidas Israel", 220, 449),
    ("AD-003", "7290022220035", "Adidas Samba OG Black", "Adidas", "Sneakers", "Adidas Israel", 260, 549),
    ("AD-004", "7290022220042", "Adidas Gazelle Bold W37", "Adidas", "Sneakers", "Adidas Israel", 240, 499),
    ("NA-001", "7290033330011", "Nautica Polo Shirt L Navy", "Nautica", "Apparel", "Nautica Israel", 80, 199),
    ("NA-002", "7290033330028", "Nautica Crew Sweat XL", "Nautica", "Apparel", "Nautica Israel", 120, 259),
    ("LT-001", "7290044440011", "Lifetime Cooler Bag 25L", "Lifetime", "Outdoor", "Lifetime Israel", 90, 199),
    ("LT-002", "7290044440028", "Lifetime Tumbler 600ml Steel", "Lifetime", "Outdoor", "Lifetime Israel", 40, 99),
]


def _upsert_dim(db, model, key_field, value, **defaults):
    obj = db.scalar(select(model).where(getattr(model, key_field) == value))
    if obj is None:
        obj = model(**{key_field: value, **defaults})
        db.add(obj)
        db.flush()
    return obj


def _wipe_demo(db):
    # Delete only fact rows that have NO source_file_id (demo rows).
    db.execute(delete(Sale).where(Sale.source_file_id.is_(None)))
    db.execute(delete(InventorySnapshot).where(InventorySnapshot.source_file_id.is_(None)))


def _store_brand_weight(store_type: str, brand: str) -> float:
    """
    Returns a multiplier on baseline daily units for (store_type, brand).
    Encodes the business pattern requested in the spec.
    """
    if brand == "Keds":
        return {"flagship": 0.6, "general": 0.8, "value": 2.4, "outlet": 2.8}.get(store_type, 1.0)
    if brand == "Adidas":
        return {"flagship": 2.6, "general": 2.2, "value": 0.6, "outlet": 0.4}.get(store_type, 1.0)
    if brand == "Nautica":
        return {"flagship": 1.0, "general": 1.0, "value": 0.5, "outlet": 0.3}.get(store_type, 1.0)
    if brand == "Lifetime":
        return {"flagship": 0.6, "general": 0.8, "value": 1.4, "outlet": 1.6}.get(store_type, 1.0)
    return 1.0


def _seed_dimensions(db):
    brands = {n: _upsert_dim(db, Brand, "name", n)
              for n in {"Keds", "Adidas", "Nautica", "Lifetime"}}
    categories = {n: _upsert_dim(db, Category, "name", n)
                  for n in {"Sneakers", "Apparel", "Outdoor"}}
    suppliers = {n: _upsert_dim(db, Supplier, "name", n)
                 for n in {"Keds Israel", "Adidas Israel", "Nautica Israel", "Lifetime Israel"}}

    stores = {}
    for code, name, region, stype in STORES:
        s = db.scalar(select(Store).where(Store.store_code == code))
        if s is None:
            s = Store(store_code=code, store_name=name, region=region, store_type=stype, active=True)
            db.add(s)
            db.flush()
        else:
            s.store_name, s.region, s.store_type = name, region, stype
        stores[code] = s

    items = {}
    for code, bc, name, brand, cat, sup, cost, price in ITEMS:
        it = db.scalar(select(Item).where(Item.item_code == code))
        if it is None:
            it = Item(
                item_code=code, barcode=bc, item_name=name,
                brand_id=brands[brand].id,
                category_id=categories[cat].id,
                supplier_id=suppliers[sup].id,
                cost_price=cost, selling_price=price, active=True,
            )
            db.add(it)
            db.flush()
        else:
            it.item_name, it.brand_id, it.category_id = name, brands[brand].id, categories[cat].id
            it.supplier_id, it.cost_price, it.selling_price = suppliers[sup].id, cost, price
        items[code] = it

    return stores, items


def _seed_sales(db, stores, items):
    today = date.today()
    days = 60
    rows = 0
    for d_offset in range(days):
        day = today - timedelta(days=days - 1 - d_offset)
        # weekday seasonality: Fri/Sat low, Thu peak
        weekday = day.weekday()
        weekday_mult = {0: 0.9, 1: 1.0, 2: 1.0, 3: 1.2, 4: 1.4, 5: 0.7, 6: 0.8}[weekday]
        for store in stores.values():
            # store size baseline
            store_mult = {"flagship": 1.4, "general": 1.0, "value": 0.9, "outlet": 0.6}.get(store.store_type, 1.0)
            for it in items.values():
                base = 2.0  # base units/day per (store, item)
                w = _store_brand_weight(store.store_type, it.brand.name)
                # add some Nautica/Lifetime stuck-item suppression in some stores
                if it.item_code in {"NA-001", "NA-002"} and store.store_type in {"value", "outlet"}:
                    w *= 0.05
                if it.item_code in {"LT-001"} and store.store_type in {"flagship", "general"}:
                    w *= 0.05

                lam = base * w * store_mult * weekday_mult
                qty = max(0, int(random.gauss(lam, max(0.4, lam * 0.3))))
                if qty <= 0:
                    continue
                gross = qty * (it.selling_price or 100)
                discount = round(gross * random.choice([0, 0, 0, 0.05, 0.1]), 2)
                net = round(gross - discount, 2)
                cost_amount = round(qty * (it.cost_price or 50), 2)
                margin = round(net - cost_amount, 2)
                db.add(Sale(
                    date=day,
                    store_id=store.id,
                    item_id=it.id,
                    barcode=it.barcode,
                    quantity=qty,
                    gross_sales=gross,
                    net_sales=net,
                    discount_amount=discount,
                    return_quantity=0.0,
                    cost_amount=cost_amount,
                    gross_margin_amount=margin,
                    source_file_id=None,
                ))
                rows += 1
    return rows


def _seed_inventory(db, stores, items):
    today = date.today()
    rows = 0
    for store in stores.values():
        for it in items.values():
            # base stock
            base_stock = 30
            if it.item_code in {"AD-001", "AD-003"} and store.store_type in {"flagship", "general"}:
                base_stock = 2  # fast_moving_low_stock alert
            if it.item_code in {"NA-001", "NA-002"} and store.store_type in {"value", "outlet"}:
                base_stock = 45  # slow_moving_high_stock
            if it.item_code == "LT-001" and store.store_type in {"flagship", "general"}:
                base_stock = 60  # stuck
            db.add(InventorySnapshot(
                snapshot_date=today,
                store_id=store.id,
                item_id=it.id,
                barcode=it.barcode,
                inventory_quantity=base_stock,
                available_quantity=base_stock,
                on_order_quantity=0 if base_stock > 5 else 24,
                source_file_id=None,
            ))
            rows += 1
    return rows


def main() -> None:
    init_db()
    with session_scope() as db:
        _wipe_demo(db)
        stores, items = _seed_dimensions(db)
        n_sales = _seed_sales(db, stores, items)
        n_inv = _seed_inventory(db, stores, items)

    print(f"Seeded demo data:")
    print(f"  stores: {len(STORES)}")
    print(f"  items:  {len(ITEMS)}")
    print(f"  sales rows: {n_sales}")
    print(f"  inventory rows: {n_inv}")
    print()
    print("Patterns:")
    print("  - Keds dominates value/outlet stores")
    print("  - Adidas dominates flagship/general stores")
    print("  - Adidas Stan Smith / Samba low stock in flagships → reorder alerts")
    print("  - Nautica + Lifetime stuck inventory in some stores")
    print()
    print("Now run:  uvicorn app.main:app --reload --port 8000")


if __name__ == "__main__":
    main()
