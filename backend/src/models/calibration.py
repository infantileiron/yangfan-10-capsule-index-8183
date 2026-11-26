from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, validates

from src.models.base import Base, new_id, utcnow


class Calibration(Base):
    """An atomic IsolationForest/model + cabinet-level threshold pair."""

    __tablename__ = "calibrations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    caliber: Mapped[str] = mapped_column(String(2), index=True)
    quantile: Mapped[float] = mapped_column(Float)
    quantile_key: Mapped[int] = mapped_column(Integer, default=0, index=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    fit_dataset_id: Mapped[str | None] = mapped_column(ForeignKey("datasets.id"), nullable=True)
    threshold_dataset_id: Mapped[str | None] = mapped_column(ForeignKey("datasets.id"), nullable=True)
    calibration_group: Mapped[str] = mapped_column(String(80), default="default", index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    stale: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    trusted: Mapped[bool] = mapped_column(Boolean, default=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_artifact: Mapped[str | None] = mapped_column(String(200), nullable=True)
    quality: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_versions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(160), default="system")
    supersedes_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease: Mapped[str | None] = mapped_column(String(36), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    @validates("quantile")
    def _sync_quantile_key(self, _key, value):
        self.quantile_key = int(round(float(value) * 10_000))
        return value
