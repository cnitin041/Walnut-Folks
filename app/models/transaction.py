import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("type IN ('credit', 'debit')", name="ck_transactions_type"),
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        CheckConstraint(
            "btrim(reference_id) <> ''",
            name="ck_transactions_reference_not_blank",
        ),
        UniqueConstraint(
            "account_id",
            "reference_id",
            name="uq_transactions_account_reference",
        ),
        UniqueConstraint("transfer_id", "type", name="uq_transactions_transfer_type"),
        Index("ix_transactions_account_created", "account_id", "created_at", "id"),
        Index(
            "ix_transactions_account_type_created",
            "account_id",
            "type",
            "created_at",
            "id",
        ),
        Index("ix_transactions_transfer_id", "transfer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transfers.id", ondelete="RESTRICT"),
        nullable=True,
    )
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    description: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        server_default=text("''"),
    )
    reference_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
