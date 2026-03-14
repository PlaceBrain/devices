from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.db.models.sensor import Sensor

from .base import BaseRepository


class SensorRepository(BaseRepository[Sensor]):
    def __init__(self, session: AsyncSession):
        super().__init__(Sensor, session)
