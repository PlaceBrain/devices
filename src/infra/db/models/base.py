import uuid

from sqlalchemy import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.core.types import IDType


class Base(DeclarativeBase):
    id: Mapped[IDType] = mapped_column(UUID, default=uuid.uuid7, primary_key=True)
