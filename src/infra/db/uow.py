import logging
from contextlib import AbstractAsyncContextManager
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.infra.db.repositories import (
    ActuatorRepository,
    DeviceRepository,
    SensorRepository,
    SensorThresholdRepository,
)

logger = logging.getLogger(__name__)


class UnitOfWork(AbstractAsyncContextManager["UnitOfWork"]):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("Session not initialized.")
        return self._session

    async def __aenter__(self) -> Self:
        logger.debug("Creating new session")
        self._session = self.session_factory()
        self.device_repository = DeviceRepository(self.session)
        self.sensor_repository = SensorRepository(self.session)
        self.sensor_threshold_repository = SensorThresholdRepository(self.session)
        self.actuator_repository = ActuatorRepository(self.session)
        return self

    async def commit(self) -> None:
        logger.debug("Committing transaction")
        await self.session.commit()

    async def rollback(self) -> None:
        logger.debug("Rolling back transaction")
        await self.session.rollback()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if exc_type:
            logger.warning("Exception occurred: %s: %s", exc_type.__name__, exc_val)
            await self.rollback()
        else:
            logger.debug("Transaction completed successfully")
            await self.commit()
        await self.session.close()
