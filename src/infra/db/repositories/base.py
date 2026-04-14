import logging
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Result, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.types import UNSET, IDType
from src.infra.db.models import Base

logger = logging.getLogger(__name__)


class BaseRepository[T: Base]:
    def __init__(self, model: type[T], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: IDType) -> T | None:
        return await self.session.get(self.model, id)

    async def find(
        self,
        filters: list[Any] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
        load_options: list[Any] | None = None,
    ) -> Sequence[T]:
        query = select(self.model)

        if filters:
            query = query.where(*filters)

        if order_by is not None:
            query = query.order_by(order_by)

        if load_options:
            query = query.options(*load_options)

        if offset is not None:
            query = query.offset(offset)

        if limit is not None:
            query = query.limit(limit)

        result = await self.session.scalars(query)
        return result.all()

    async def get_all(self, **filter_by: Any) -> Sequence[T]:
        query = select(self.model).filter_by(**filter_by)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_one_or_none(self, **filter_by: Any) -> T | None:
        query = select(self.model).filter_by(**filter_by)
        result: Result[tuple[T]] = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(self, **data: Any) -> T:
        entity = self.model(**data)
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(self, id: IDType, **data: Any) -> T:
        result = await self.session.execute(
            update(self.model).where(self.model.id == id).values(**data).returning(self.model)
        )
        updated_entity = result.scalar_one_or_none()
        if not updated_entity:
            raise ValueError(f"Entity with id {id} not found")
        await self.session.flush()
        return updated_entity

    async def patch(self, id: IDType, **data: Any) -> T:
        filtered_data = {k: v for k, v in data.items() if v is not UNSET}
        return await self.update(id, **filtered_data)

    async def delete(self, entity: T) -> None:
        await self.session.delete(entity)
        await self.session.flush()

    async def count(self, filters: list[Any] | None = None) -> int:
        query = select(func.count()).select_from(self.model)
        if filters:
            query = query.where(*filters)
        count_result = await self.session.execute(query)
        return count_result.scalar_one()
