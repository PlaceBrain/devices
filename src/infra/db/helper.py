from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import PostgresConfig


class DatabaseHelper:
    def __init__(self, config: PostgresConfig) -> None:
        self.engine = create_async_engine(
            url=str(config.url),
            echo=config.echo,
            echo_pool=config.echo_pool,
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_pre_ping=config.pool_pre_ping,
            pool_timeout=config.pool_timeout,
        )
        self.async_session_factory = async_sessionmaker[AsyncSession](
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    async def dispose(self) -> None:
        await self.engine.dispose()
