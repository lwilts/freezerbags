"""Business logic: everything that touches Item/Batch rows.

Kept separate from routes.py so the FIFO consumption logic and validation
rules have one home and are easy to unit test without spinning up FastAPI.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .models import Item, Batch

LONDON = ZoneInfo("Europe/London")

MAX_NAME_LEN = 80
MIN_PORTIONS = 1
MAX_PORTIONS = 99

# Age-badge thresholds, in days since the oldest batch was frozen.
AMBER_AFTER_DAYS = 90
RED_AFTER_DAYS = 180


class ValidationError(ValueError):
    """Raised for bad user input; routes.py turns this into an inline error."""


def today_london() -> dt.date:
    return dt.datetime.now(LONDON).date()


def _clean_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise ValidationError("Please enter a food description.")
    if len(name) > MAX_NAME_LEN:
        raise ValidationError(f"Description must be {MAX_NAME_LEN} characters or fewer.")
    return name


def _clean_portions(portions: int) -> int:
    try:
        portions = int(portions)
    except (TypeError, ValueError):
        raise ValidationError("Portions must be a number.")
    if portions < MIN_PORTIONS or portions > MAX_PORTIONS:
        raise ValidationError(f"Portions must be between {MIN_PORTIONS} and {MAX_PORTIONS}.")
    return portions


@dataclass
class ItemView:
    """Read-only, template-friendly summary of an item and its batches."""

    id: int
    name: str
    total_portions: int
    oldest_frozen_on: dt.date
    age_days: int
    tier: str  # "fresh" | "amber" | "red"


def format_age(age_days: int) -> str:
    """Human-friendly age for the badge, e.g. "2 weeks", "3 months"."""
    if age_days <= 0:
        return "today"
    if age_days == 1:
        return "1 day"
    if age_days < 14:
        return f"{age_days} days"
    if age_days < 60:
        weeks = age_days // 7
        return f"{weeks} week" + ("s" if weeks != 1 else "")
    months = age_days // 30
    return f"{months} month" + ("s" if months != 1 else "")


def _age_tier(age_days: int) -> str:
    if age_days >= RED_AFTER_DAYS:
        return "red"
    if age_days >= AMBER_AFTER_DAYS:
        return "amber"
    return "fresh"


def _to_view(item: Item, *, today: dt.date) -> ItemView:
    total = sum(b.portions for b in item.batches)
    oldest = min(b.frozen_on for b in item.batches)
    age_days = (today - oldest).days
    return ItemView(
        id=item.id,
        name=item.name,
        total_portions=total,
        oldest_frozen_on=oldest,
        age_days=age_days,
        tier=_age_tier(age_days),
    )


def list_active(session: Session) -> list[ItemView]:
    """Active items, oldest frozen batch first -- what most needs eating soonest."""
    today = today_london()
    items = (
        session.execute(
            select(Item).where(Item.archived_at.is_(None)).order_by(Item.created_at)
        )
        .scalars()
        .all()
    )
    # An item can only be active with at least one batch (see _archive_if_empty),
    # but guard anyway so a stray empty row never breaks the whole list render.
    views = [_to_view(item, today=today) for item in items if item.batches]
    views.sort(key=lambda v: v.oldest_frozen_on)
    return views


def _find_active_item_by_name(session: Session, name: str) -> Item | None:
    return session.execute(
        select(Item).where(
            Item.archived_at.is_(None),
            func.lower(Item.name) == name.lower(),
        )
    ).scalar_one_or_none()


def add_item(session: Session, name: str, portions: int) -> Item:
    """Create a new item, or top up a same-named active item instead."""
    name = _clean_name(name)
    portions = _clean_portions(portions)

    existing = _find_active_item_by_name(session, name)
    if existing is not None:
        session.add(Batch(item_id=existing.id, portions=portions, frozen_on=today_london()))
        return existing

    item = Item(name=name)
    session.add(item)
    session.flush()  # assign item.id for the batch FK
    session.add(Batch(item_id=item.id, portions=portions, frozen_on=today_london()))
    return item


def _get_active_item(session: Session, item_id: int) -> Item:
    item = session.get(Item, item_id)
    if item is None or item.archived_at is not None:
        raise ValidationError("That item is no longer in the freezer.")
    return item


def add_batch(session: Session, item_id: int, portions: int) -> Item:
    portions = _clean_portions(portions)
    item = _get_active_item(session, item_id)
    session.add(Batch(item_id=item.id, portions=portions, frozen_on=today_london()))
    return item


def edit_item(session: Session, item_id: int, name: str, frozen_on: dt.date) -> Item:
    """Rename an item and/or correct its oldest batch's freeze date.

    "Frozen on" only has one clear meaning once an item has several batches:
    the oldest one, since that's what's shown and what drives the age badge.
    """
    name = _clean_name(name)
    item = _get_active_item(session, item_id)

    if frozen_on > today_london():
        raise ValidationError("Frozen date can't be in the future.")

    other = _find_active_item_by_name(session, name)
    if other is not None and other.id != item.id:
        raise ValidationError(f'"{name}" is already in the freezer — use "Add to" instead.')

    oldest = min(item.batches, key=lambda b: b.frozen_on)
    oldest.frozen_on = frozen_on
    item.name = name
    return item


def _archive_if_empty(item: Item) -> None:
    if not item.batches:
        item.archived_at = dt.datetime.now(LONDON)


def eat(session: Session, item_id: int, portions: int) -> Item:
    """Consume `portions`, draining the oldest batch(es) first."""
    portions = _clean_portions(portions)
    item = _get_active_item(session, item_id)

    available = sum(b.portions for b in item.batches)
    if portions > available:
        raise ValidationError(f"Only {available} portion(s) left.")

    remaining = portions
    # item.batches is ordered oldest-first (see Item.batches relationship).
    for batch in list(item.batches):
        if remaining <= 0:
            break
        take = min(batch.portions, remaining)
        batch.portions -= take
        remaining -= take
        if batch.portions == 0:
            item.batches.remove(batch)
            session.delete(batch)

    _archive_if_empty(item)
    return item


def discard(session: Session, item_id: int) -> Item:
    item = _get_active_item(session, item_id)
    for batch in list(item.batches):
        item.batches.remove(batch)
        session.delete(batch)
    item.archived_at = dt.datetime.now(LONDON)
    return item
