import enum

from sqlalchemy import UUID, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column

from src.core.types import IDType

from .base import Base


class ValueTypeEnum(enum.StrEnum):
    NUMBER = "number"
    BOOLEAN = "boolean"


class Sensor(Base):
    __tablename__ = "sensors"

    device_id: Mapped[IDType] = mapped_column(
        UUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    value_type: Mapped[ValueTypeEnum] = mapped_column(
        SQLAlchemyEnum(ValueTypeEnum), nullable=False, default=ValueTypeEnum.NUMBER
    )
    unit_label: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    precision: Mapped[int] = mapped_column(Integer, default=2, nullable=False)

    __table_args__ = (UniqueConstraint("device_id", "key"),)
