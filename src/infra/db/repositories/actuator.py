from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.db.models.actuator import Actuator

from .base import BaseRepository


class ActuatorRepository(BaseRepository[Actuator]):
    def __init__(self, session: AsyncSession):
        super().__init__(Actuator, session)
