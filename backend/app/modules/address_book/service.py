from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.modules.address_book.repository import AddressBookRepository
from app.modules.address_book.schemas import AddressEntryCreate, AddressEntryResponse

logger = logging.getLogger(__name__)


class AddressBookService:
    def __init__(self, repo: AddressBookRepository | None = None) -> None:
        self.repo = repo or AddressBookRepository()

    def create(
        self,
        db: Session,
        *,
        user_id: int,
        payload: AddressEntryCreate,
    ) -> AddressEntryResponse:
        entry = self.repo.create(
            db,
            user_id=user_id,
            label=payload.label,
            full_name=payload.full_name,
            phone=payload.phone,
            email=payload.email,
            company_name=payload.company_name,
            country=payload.country.upper(),
            city=payload.city,
            address_line1=payload.address_line1,
            address_line2=payload.address_line2,
            postal_code=payload.postal_code,
            is_default=payload.is_default,
        )
        db.commit()
        logger.info("Address entry created: user_id=%s id=%s", user_id, entry.id)
        return AddressEntryResponse.model_validate(entry)

    def list_addresses(self, db: Session, *, user_id: int) -> list[AddressEntryResponse]:
        entries = self.repo.list_for_user(db, user_id=user_id)
        return [AddressEntryResponse.model_validate(e) for e in entries]

    def delete(self, db: Session, *, user_id: int, entry_id: int) -> None:
        found = self.repo.delete(db, entry_id=entry_id, user_id=user_id)
        if not found:
            raise NotFoundError("Адрес не найден")
        db.commit()
        logger.info("Address entry deleted: user_id=%s id=%s", user_id, entry_id)
