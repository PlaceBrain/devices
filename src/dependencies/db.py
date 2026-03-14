from collections.abc import AsyncIterable

from dishka import Provider, Scope, provide

from src.core.config import Settings
from src.infra.db import DatabaseHelper, UnitOfWork


class DBProvider(Provider):
    @provide(scope=Scope.APP)
    async def provide_db_helper(self, settings: Settings) -> AsyncIterable[DatabaseHelper]:
        db_helper = DatabaseHelper(settings.database)
        yield db_helper
        await db_helper.dispose()

    @provide(scope=Scope.REQUEST)
    def provide_uow(self, db_helper: DatabaseHelper) -> UnitOfWork:
        return UnitOfWork(db_helper.async_session_factory)
