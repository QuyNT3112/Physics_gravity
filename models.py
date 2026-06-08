"""
models.py – SQLAlchemy ORM models for the General Relativity Simulator.

Tables:
  UserSession        – User session tracking
  SimulationRun      – Every simulation execution (parameters)
  SimulationResult   – Computed result data (path points, stats)
  AnalyticsSummary   – ETL-aggregated daily statistics (materialized)
  ParameterHeatmap   – Popular parameter combinations
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, ForeignKey,
    Index, Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from database import Base


# ── Utility ─────────────────────────────────────────────────────────────────────

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _new_uuid() -> str:
    return str(uuid.uuid4())


# ── Models ───────────────────────────────────────────────────────────────────────

class UserSession(Base):
    """
    Tracks browser sessions to understand user engagement patterns.
    session_id is generated client-side (localStorage UUID).
    """
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=_new_uuid)
    ip_address: Mapped[str | None] = mapped_column(String(45))          # supports IPv6
    user_agent: Mapped[str | None] = mapped_column(String(512))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)
    total_runs: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    runs: Mapped[list["SimulationRun"]] = relationship("SimulationRun", back_populates="session", lazy="dynamic")

    __table_args__ = (
        Index("ix_user_sessions_session_id", "session_id"),
        Index("ix_user_sessions_first_seen", "first_seen"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "total_runs": self.total_runs,
        }


class SimulationRun(Base):
    """
    Records every simulation execution with its input parameters.
    sim_type: 'geodesic' | 'light_ray' | 'time_dilation' | 'curvature' | 'waves' | 'schwarzschild'
    """
    __tablename__ = "simulation_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=_new_uuid)
    session_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("user_sessions.session_id"), nullable=True)
    sim_type: Mapped[str] = mapped_column(String(30), nullable=False)   # geodesic, light_ray, etc.
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False)       # input params as JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc, index=True)

    # Relationships
    session: Mapped["UserSession | None"] = relationship("UserSession", back_populates="runs")
    result: Mapped["SimulationResult | None"] = relationship(
        "SimulationResult", back_populates="run", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_sim_runs_sim_type", "sim_type"),
        Index("ix_sim_runs_created_at", "created_at"),
        Index("ix_sim_runs_session_type", "session_id", "sim_type"),
    )

    def to_dict(self, include_result: bool = False) -> dict:
        d = {
            "id": self.id,
            "run_uuid": self.run_uuid,
            "session_id": self.session_id,
            "sim_type": self.sim_type,
            "parameters": self.parameters,
            "created_at": self.created_at.isoformat(),
        }
        if include_result and self.result:
            d["result"] = self.result.to_dict(include_path=False)
        return d


class SimulationResult(Base):
    """
    Stores computed output of a simulation run.
    result_data holds the full JSON response (path points, etc.)
    Heavy data is stored but path_points_count and execution_ms are indexed for analytics.
    """
    __tablename__ = "simulation_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("simulation_runs.id", ondelete="CASCADE"), unique=True)
    result_summary: Mapped[dict] = mapped_column(JSON, nullable=False)   # key stats (no heavy path data)
    result_data: Mapped[dict | None] = mapped_column(JSON, nullable=True) # full result with path
    path_points_count: Mapped[int | None] = mapped_column(Integer)
    execution_ms: Mapped[float | None] = mapped_column(Float)
    captured: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc)

    # Relationship
    run: Mapped["SimulationRun"] = relationship("SimulationRun", back_populates="result")

    __table_args__ = (
        Index("ix_sim_results_run_id", "run_id"),
        Index("ix_sim_results_execution_ms", "execution_ms"),
        Index("ix_sim_results_captured", "captured"),
    )

    def to_dict(self, include_path: bool = False) -> dict:
        d = {
            "id": self.id,
            "run_id": self.run_id,
            "result_summary": self.result_summary,
            "path_points_count": self.path_points_count,
            "execution_ms": self.execution_ms,
            "captured": self.captured,
            "created_at": self.created_at.isoformat(),
        }
        if include_path and self.result_data:
            d["result_data"] = self.result_data
        return d


class AnalyticsSummary(Base):
    """
    ETL-materialized daily statistics per simulation type.
    Populated by etl_pipeline.py – never written directly by API routes.
    """
    __tablename__ = "analytics_summary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False)        # YYYY-MM-DD
    sim_type: Mapped[str] = mapped_column(String(30), nullable=False)
    total_runs: Mapped[int] = mapped_column(Integer, default=0)
    unique_sessions: Mapped[int] = mapped_column(Integer, default=0)
    avg_execution_ms: Mapped[float | None] = mapped_column(Float)
    median_execution_ms: Mapped[float | None] = mapped_column(Float)
    capture_rate: Mapped[float | None] = mapped_column(Float)           # % of captured particles
    avg_path_points: Mapped[float | None] = mapped_column(Float)
    popular_params: Mapped[dict | None] = mapped_column(JSON)            # most common param values
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    __table_args__ = (
        Index("ix_analytics_date_type", "date", "sim_type", unique=True),
        Index("ix_analytics_date", "date"),
    )

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "sim_type": self.sim_type,
            "total_runs": self.total_runs,
            "unique_sessions": self.unique_sessions,
            "avg_execution_ms": self.avg_execution_ms,
            "median_execution_ms": self.median_execution_ms,
            "capture_rate": self.capture_rate,
            "avg_path_points": self.avg_path_points,
            "popular_params": self.popular_params,
            "updated_at": self.updated_at.isoformat(),
        }


class ParameterHeatmap(Base):
    """
    Tracks how often specific parameter combinations are used.
    Used to power the heatmap analytics endpoint.
    Updated incrementally by ETL pipeline.
    """
    __tablename__ = "parameter_heatmap"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sim_type: Mapped[str] = mapped_column(String(30), nullable=False)
    param_key: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "r0"
    param_value: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. "6.0"
    usage_count: Mapped[int] = mapped_column(Integer, default=1)
    capture_count: Mapped[int] = mapped_column(Integer, default=0)       # times this led to capture
    last_used: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    __table_args__ = (
        Index("ix_heatmap_type_key_val", "sim_type", "param_key", "param_value", unique=True),
        Index("ix_heatmap_type_key", "sim_type", "param_key"),
    )

    def to_dict(self) -> dict:
        return {
            "sim_type": self.sim_type,
            "param_key": self.param_key,
            "param_value": self.param_value,
            "usage_count": self.usage_count,
            "capture_count": self.capture_count,
            "capture_rate": self.capture_count / self.usage_count if self.usage_count else 0,
            "last_used": self.last_used.isoformat(),
        }
