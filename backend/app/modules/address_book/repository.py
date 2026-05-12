from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from app.modules.address_book.models import AddressBookEntry


class AddressBookRepository:
    def create(
        self,
        db: Session,
        *,
        user_id: int,
        label: str | None,
        full_name: str,
        phone: str,
        email: str | None,
        company_name: str | None,
        country: str,
        city: str,
        address_line1: str,
        address_line2: str | None,
        postal_code: str | None,
        is_default: bool,
    ) -> AddressBookEntry:
        if is_default:
            db.execute(
                sa_update(AddressBookEntry)
                .where(AddressBookEntry.user_id == user_id)
                .values(is_default=False)
            )
        entry = AddressBookEntry(
            user_id=user_id,
            label=label,
            full_name=full_name,
            phone=phone,
            email=email,
            company_name=company_name,
            country=country,
            city=city,
            address_line1=address_line1,
            address_line2=address_line2,
            postal_code=postal_code,
            is_default=is_default,
        )
        db.add(entry)
        db.flush()
        return entry

    def list_for_user(self, db: Session, *, user_id: int) -> Sequence[AddressBookEntry]:
        return db.scalars(
            select(AddressBookEntry)
            .where(AddressBookEntry.user_id == user_id)
            .order_by(AddressBookEntry.is_default.desc(), AddressBookEntry.created_at.desc())
        ).all()

    def get_by_id(self, db: Session, *, entry_id: int, user_id: int) -> AddressBookEntry | None:
        return db.scalar(
            select(AddressBookEntry).where(
                AddressBookEntry.id == entry_id,
                AddressBookEntry.user_id == user_id,
            )
        )

    def delete(self, db: Session, *, entry_id: int, user_id: int) -> bool:
        entry = self.get_by_id(db, entry_id=entry_id, user_id=user_id)
        if entry is None:
            return False
        db.delete(entry)
        return True
