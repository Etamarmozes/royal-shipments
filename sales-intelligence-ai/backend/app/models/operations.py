from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ImportLog(Base):
    __tablename__ = "import_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_name: Mapped[str] = mapped_column(String(512))
    original_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    report_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))  # success | partial | failed
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    data_date_min: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_date_max: Mapped[date | None] = mapped_column(Date, nullable=True)
    rows_detected: Mapped[int] = mapped_column(Integer, default=0)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0)
    rows_failed: Mapped[int] = mapped_column(Integer, default=0)
    warnings: Mapped[str | None] = mapped_column(Text, nullable=True)
    errors: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class GeneratedReport(Base):
    __tablename__ = "generated_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(512))
    file_path: Mapped[str] = mapped_column(String(1024))
    format: Mapped[str] = mapped_column(String(16))
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    generated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parameters_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class AIAnalysisLog(Base):
    __tablename__ = "ai_analysis_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    tools_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    data_sources_used: Mapped[str | None] = mapped_column(Text, nullable=True)
