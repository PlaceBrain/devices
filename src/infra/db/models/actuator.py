import enum

from sqlalchemy import UUID, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.types import IDType

from .base import Base


class ActuatorValueTypeEnum(enum.StrEnum):
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"


class Actuator(Base):
    __tablename__ = "actuators"

    device_id: Mapped[IDType] = mapped_column(
        UUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    value_type: Mapped[ActuatorValueTypeEnum] = mapped_column(
        SQLAlchemyEnum(ActuatorValueTypeEnum), nullable=False, default=ActuatorValueTypeEnum.NUMBER
    )
    unit_label: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    precision: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    step: Mapped[float | None] = mapped_column(Float, nullable=True)
    enum_options: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (UniqueConstraint("device_id", "key"),)
