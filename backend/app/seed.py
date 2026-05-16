"""Seed the database with the 6 shipments + 8 containers from the brief."""
from datetime import date, datetime
from .database import Base, engine, SessionLocal
from .models import Shipment, Container, User


SHIPMENTS = [
    {
        "shp_id": "SHP-006",
        "supplier": "Nandan Terry / A&M Global",
        "goods_description": "מגבות 100% Cotton — מכולה 1",
        "origin_country": "הודו",
        "origin_port": "Mundra",
        "shipping_channel": "sea",
        "current_stage": 5,
        "stage_status": "בוקינג",
        "customs_broker": "ICL Israel Cargo",
        "eta_israel": None,
    },
    {
        "shp_id": "SHP-007",
        "supplier": "Nandan Terry / A&M Global",
        "goods_description": "מגבות 100% Cotton — מכולה 2",
        "origin_country": "הודו",
        "origin_port": "Mundra",
        "shipping_channel": "sea",
        "current_stage": 5,
        "stage_status": "בוקינג",
        "customs_broker": "ICL Israel Cargo",
        "eta_israel": None,
    },
    {
        "shp_id": "SHP-008",
        "supplier": "ULAC / Puma United Canada",
        "goods_description": "Puma: גרביים, כובעים, תיקים — 18,660 יח'",
        "origin_country": "קנדה",
        "shipping_channel": "sea",
        "current_stage": 7,
        "stage_status": "עדכונים שוטפים",
        "customs_broker": "Diana Sisti / Suretrack",
        "eta_israel": date(2026, 5, 5),
    },
    {
        "shp_id": "SHP-009",
        "supplier": "Polder / Guangdong Kenries",
        "goods_description": "Ironing Boards 17”×49” — 72 קופסאות",
        "origin_country": "סין",
        "shipping_channel": "sea",
        "current_stage": 7,
        "stage_status": "עדכונים שוטפים",
        "customs_broker": "Eli Line — Eli Cohen",
        "eta_israel": date(2026, 5, 14),
    },
    {
        "shp_id": "SHP-010",
        "supplier": "Nandan Terry / A&M Global",
        "goods_description": "מגבות — מכולה 3",
        "origin_country": "הודו",
        "shipping_channel": "sea",
        "current_stage": 5,
        "stage_status": "בוקינג",
        "customs_broker": "ICL Israel Cargo",
        "eta_israel": None,
    },
    {
        "shp_id": "SHP-011",
        "supplier": "Nandan Terry / A&M Global",
        "goods_description": "מגבות — מכולה 4",
        "origin_country": "הודו",
        "shipping_channel": "sea",
        "current_stage": 5,
        "stage_status": "בוקינג",
        "customs_broker": "ICL Israel Cargo",
        "eta_israel": None,
    },
]


CONTAINERS = [
    {"shp": "SHP-006", "container_number": "MSNU5649034", "container_type": "40HC", "boxes_total": 939, "gross_weight_kg": 7512, "cbm": 60.85},
    {"shp": "SHP-007", "container_number": "CAAU7102106", "container_type": "40HC", "boxes_total": 1048, "gross_weight_kg": 7262, "cbm": 52.81},
    {"shp": "SHP-008", "container_number": "BOL 4061194", "container_type": None, "boxes_total": 389, "gross_weight_kg": 7257, "cbm": None},
    {"shp": "SHP-009", "container_number": "EMCU0105518", "container_type": "40HQ", "boxes_total": 24, "gross_weight_kg": 6512, "cbm": 43.44},
    {"shp": "SHP-009", "container_number": "EITU9224730", "container_type": "40HQ", "boxes_total": 24, "gross_weight_kg": 6512, "cbm": 43.44},
    {"shp": "SHP-009", "container_number": "EGSU9557499", "container_type": "40HQ", "boxes_total": 24, "gross_weight_kg": 6512, "cbm": 43.44},
    {"shp": "SHP-010", "container_number": "MSMU6656219", "container_type": "40HC", "boxes_total": 1342, "gross_weight_kg": 8521, "cbm": 61.67},
    {"shp": "SHP-011", "container_number": "MSDU6282914", "container_type": "40HC", "boxes_total": 786, "gross_weight_kg": 8017, "cbm": 55.43},
]


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Shipment).count() > 0:
            print("DB already seeded. Skipping.")
            return

        shp_map = {}
        for sd in SHIPMENTS:
            s = Shipment(
                shp_id=sd["shp_id"],
                supplier=sd.get("supplier"),
                goods_description=sd.get("goods_description"),
                origin_country=sd.get("origin_country"),
                origin_port=sd.get("origin_port"),
                shipping_channel=sd.get("shipping_channel"),
                current_stage=sd.get("current_stage"),
                stage_status=sd.get("stage_status"),
                customs_broker=sd.get("customs_broker"),
                eta_israel=sd.get("eta_israel"),
                created_date=date.today(),
                creation_source="excel_import",
                last_update_source="manual",
                paperwork_complete=False,
                approval_status="ממתין",
                delay_status=False,
                extra_work_required=False,
                updated_by="system",
            )
            db.add(s)
            db.flush()
            shp_map[sd["shp_id"]] = s.id

        for cd in CONTAINERS:
            c = Container(
                shipment_id=shp_map[cd["shp"]],
                container_number=cd["container_number"],
                container_type=cd["container_type"],
                cbm=cd["cbm"],
                boxes_total=cd["boxes_total"],
                gross_weight_kg=cd["gross_weight_kg"],
                container_status="בדרך",
                unloading_priority="רגיל",
                extra_work_required=False,
                updated_by="system",
            )
            db.add(c)

        if not db.query(User).first():
            db.add(User(
                name="מנהל ראשי",
                email="admin@royallinen.co.il",
                role="admin",
                active=True,
            ))

        db.commit()
        print(f"Seeded {len(SHIPMENTS)} shipments and {len(CONTAINERS)} containers.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
