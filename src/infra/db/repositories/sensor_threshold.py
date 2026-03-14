from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.db.models.sensor_threshold import SensorThreshold

from .base import BaseRepository


class SensorThresholdRepository(BaseRepository[SensorThreshold]):
    def __init__(self, session: AsyncSession):
        super().__init__(SensorThreshold, session)
