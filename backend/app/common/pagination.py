from __future__ import annotations

import math
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Номер страницы (начиная с 1)")
    size: int = Field(default=20, ge=1, le=100, description="Элементов на странице (макс 100)")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        params: PageParams,
    ) -> "PaginatedResponse[T]":
        pages = math.ceil(total / params.size) if total > 0 else 1
        return cls(
            items=items,
            total=total,
            page=params.page,
            size=params.size,
            pages=pages,
        )
