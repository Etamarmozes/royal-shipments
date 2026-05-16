from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.dashboard import (
    DashboardKpis, ForecastWeek, ActionItem, EmailSummary, ExtraWorkSummary,
)
from ..services import dashboard_service, forecast_service, daily_forecast_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpis", response_model=DashboardKpis)
def get_kpis(db: Session = Depends(get_db)):
    return dashboard_service.kpis(db)


@router.get("/forecast-8-weeks", response_model=List[ForecastWeek])
def forecast_8_weeks(db: Session = Depends(get_db)):
    return forecast_service.forecast_8_weeks(db)


@router.get("/email-summary", response_model=EmailSummary)
def email_summary(db: Session = Depends(get_db)):
    return dashboard_service.email_summary(db)


@router.get("/extra-work-summary", response_model=ExtraWorkSummary)
def extra_work_summary(db: Session = Depends(get_db)):
    return dashboard_service.extra_work_summary(db)


@router.get("/action-items", response_model=List[ActionItem])
def action_items(db: Session = Depends(get_db)):
    return dashboard_service.action_items(db)


@router.get("/pallet-forecast-daily")
def pallet_forecast_daily(days: int = Query(14, ge=1, le=60), db: Session = Depends(get_db)):
    """Day-by-day pallet forecast for the next N days (default 14)."""
    return daily_forecast_service.daily_pallet_forecast(db, days=days)


@router.get("/pallet-kpis")
def pallet_kpis(db: Session = Depends(get_db)):
    """KPIs for the warehouse: pallets today / tomorrow / 7d / missing data."""
    return daily_forecast_service.daily_kpis(db)
