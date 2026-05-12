from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.modules.address_book.schemas import AddressEntryCreate, AddressEntryResponse
from app.modules.address_book.service import AddressBookService

router = APIRouter(prefix="/profile/addresses", tags=["address-book"])
_service = AddressBookService()


@router.get("", response_model=list[AddressEntryResponse], summary="Мои адреса")
def list_addresses(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[AddressEntryResponse]:
    return _service.list_addresses(db, user_id=current_user_id)


@router.post("", response_model=AddressEntryResponse, status_code=201, summary="Добавить адрес")
def create_address(
    payload: AddressEntryCreate,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AddressEntryResponse:
    return _service.create(db, user_id=current_user_id, payload=payload)


@router.delete("/{entry_id}", status_code=204, summary="Удалить адрес")
def delete_address(
    entry_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None:
    _service.delete(db, user_id=current_user_id, entry_id=entry_id)
