from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.container import ContainerCreate, ContainerUpdate, ContainerRead
from ..services import container_service, pallet_service, data_quality_service
from ..services.auth_service import require_permission
from ..models import User

router = APIRouter(prefix="/containers", tags=["containers"])


@router.get("", response_model=List[ContainerRead])
def list_containers(
    search: Optional[str] = None,
    status: Optional[str] = None,
    supplier: Optional[str] = None,
    extra_work_only: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    return container_service.list_containers(
        db, search=search, status=status, supplier=supplier,
        extra_work_only=extra_work_only,
    )


@router.get("/{container_id}", response_model=ContainerRead)
def get_container(container_id: int, db: Session = Depends(get_db)):
    c = container_service.get_container(db, container_id)
    return container_service.enrich_container(c)


@router.post("", response_model=ContainerRead)
def create_container(
    payload: ContainerCreate, db: Session = Depends(get_db),
    actor: User = Depends(require_permission("container.create")),
):
    c = container_service.create_container(
        db, payload, created_by=actor.full_name or actor.username,
    )
    return container_service.enrich_container(c)


@router.put("/{container_id}", response_model=ContainerRead)
def update_container(
    container_id: int, payload: ContainerUpdate, db: Session = Depends(get_db),
    actor: User = Depends(require_permission("container.update")),
):
    c = container_service.update_container(
        db, container_id, payload,
        updated_by=actor.full_name or actor.username, source="manual",
    )
    return container_service.enrich_container(c)


@router.delete("/{container_id}")
def delete_container(
    container_id: int, db: Session = Depends(get_db),
    actor: User = Depends(require_permission("container.delete")),
):
    container_service.delete_container(
        db, container_id, deleted_by=actor.full_name or actor.username,
    )
    return {"ok": True}


@router.post("/{container_id}/calculate-pallets")
def calculate_pallets(container_id: int, db: Session = Depends(get_db)):
    """Run a fresh pallet calc on the container, persist results, and return
    the full breakdown (euro + industrial + recommendation)."""
    c = container_service.get_container(db, container_id)
    result = pallet_service.apply_to_container(c)
    db.commit()
    return {
        "container_id": c.id,
        "container_number": c.container_number,
        "method": result.method,
        "cartons_total": result.cartons_total,
        "carton_length_cm": result.carton_length_cm,
        "carton_width_cm": result.carton_width_cm,
        "carton_height_cm": result.carton_height_cm,
        "euro": result.euro.__dict__ if result.euro else None,
        "industrial": result.industrial.__dict__ if result.industrial else None,
        "recommended_pallet_type": result.recommended_pallet_type,
        "estimated_pallets_final": result.estimated_pallets_final,
        "notes": result.notes,
    }


@router.get("/{container_id}/data-quality")
def container_data_quality(container_id: int, db: Session = Depends(get_db)):
    c = container_service.get_container(db, container_id)
    return data_quality_service.container_quality(c)


@router.get("/{container_id}/pallet-breakdown")
def pallet_breakdown(container_id: int, db: Session = Depends(get_db)):
    """Get the same calc breakdown WITHOUT mutating DB — useful for the UI
    to preview before the user changes inputs."""
    c = container_service.get_container(db, container_id)
    result = pallet_service.calculate(
        cartons_total=c.boxes_total,
        carton_length_cm=c.carton_length_cm,
        carton_width_cm=c.carton_width_cm,
        carton_height_cm=c.carton_height_cm,
        cbm=c.cbm,
        pallet_type_preference=c.pallet_type_preference or "auto",
    )
    return {
        "container_id": c.id,
        "container_number": c.container_number,
        "method": result.method,
        "cartons_total": result.cartons_total,
        "carton_length_cm": result.carton_length_cm,
        "carton_width_cm": result.carton_width_cm,
        "carton_height_cm": result.carton_height_cm,
        "euro": result.euro.__dict__ if result.euro else None,
        "industrial": result.industrial.__dict__ if result.industrial else None,
        "recommended_pallet_type": result.recommended_pallet_type,
        "estimated_pallets_final": result.estimated_pallets_final,
        "notes": result.notes,
    }
