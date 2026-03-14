import enum

from sqlalchemy import UUID, Float, ForeignKey
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column

from src.core.types import IDType

from .base import Base


class ThresholdTypeEnum(enum.StrEnum):
    MIN = "min"
    MAX = "max"


class ThresholdSeverityEnum(enum.StrEnum):
    WARNING = "warning"
    CRITICAL = "critical"


class SensorThreshold(Base):
    __tablename__ = "sensor_thresholds"

    sensor_id: Mapped[IDType] = mapped_column(
        UUID, ForeignKey("sensors.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[ThresholdTypeEnum] = mapped_column(
        SQLAlchemyEnum(ThresholdTypeEnum), nullable=False
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[ThresholdSeverityEnum] = mapped_column(
        SQLAlchemyEnum(ThresholdSeverityEnum), nullable=False, default=ThresholdSeverityEnum.WARNING
    )
