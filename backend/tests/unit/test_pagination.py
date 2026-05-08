from __future__ import annotations

import pytest

from app.common.pagination import PageParams, PaginatedResponse


class TestPageParams:
    def test_default_values(self):
        params = PageParams()
        assert params.page == 1
        assert params.size == 20

    def test_offset_page1(self):
        params = PageParams(page=1, size=20)
        assert params.offset == 0

    def test_offset_page2(self):
        params = PageParams(page=2, size=20)
        assert params.offset == 20

    def test_offset_page3_size10(self):
        params = PageParams(page=3, size=10)
        assert params.offset == 20

    def test_min_page_validation(self):
        with pytest.raises(Exception):
            PageParams(page=0)

    def test_max_size_validation(self):
        with pytest.raises(Exception):
            PageParams(size=101)

    def test_min_size_validation(self):
        with pytest.raises(Exception):
            PageParams(size=0)


class TestPaginatedResponse:
    def test_create_single_page(self):
        result = PaginatedResponse.create(
            items=["a", "b"],
            total=2,
            params=PageParams(page=1, size=10),
        )
        assert result.total == 2
        assert result.page == 1
        assert result.size == 10
        assert result.pages == 1
        assert result.items == ["a", "b"]

    def test_create_multiple_pages(self):
        result = PaginatedResponse.create(
            items=list(range(10)),
            total=25,
            params=PageParams(page=1, size=10),
        )
        assert result.pages == 3

    def test_create_exact_pages(self):
        result = PaginatedResponse.create(
            items=list(range(10)),
            total=20,
            params=PageParams(page=1, size=10),
        )
        assert result.pages == 2

    def test_create_empty_result(self):
        result = PaginatedResponse.create(
            items=[],
            total=0,
            params=PageParams(page=1, size=20),
        )
        assert result.pages == 1
        assert result.items == []

    def test_create_page_number_preserved(self):
        result = PaginatedResponse.create(
            items=["x"],
            total=50,
            params=PageParams(page=3, size=10),
        )
        assert result.page == 3
