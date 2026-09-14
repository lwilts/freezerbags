from __future__ import annotations

import datetime as dt

from sqlalchemy import ForeignKey, Integer, String, Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    archived_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    batches: Mapped[list["Batch"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="Batch.frozen_on, Batch.id",
    )


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    portions: Mapped[int] = mapped_column(Integer, nullable=False)
    frozen_on: Mapped[dt.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    item: Mapped["Item"] = relationship(back_populates="batches")
