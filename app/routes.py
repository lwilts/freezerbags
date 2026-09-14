from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Form, Query, Request
from fastapi.templating import Jinja2Templates

from . import services
from .db import get_session

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
templates.env.filters["age"] = services.format_age
templates.env.filters["dayshort"] = lambda d: d.strftime("%-d %b")

# Query param shared by every route below: which order the list renders in.
# Threaded through as a URL query param (not a form field) so the sort
# toggle can swap the list with a plain hx-get, and every mutating action's
# hx-post can carry the current sort along so the list doesn't jump back
# to the default order after an eat/add/edit/discard.
SortParam = Query(services.DEFAULT_SORT)


def _list_context(sort: str, error: str | None = None) -> dict:
    with get_session() as session:
        items = services.list_active(session, sort=sort)
    return {"items": items, "error": error, "today": services.today_london(), "sort": sort}


@router.get("/")
def index(request: Request, sort: str = SortParam):
    return templates.TemplateResponse(request, "index.html", _list_context(sort))


@router.get("/items")
def list_items(request: Request, sort: str = SortParam):
    """Fragment-only endpoint the sort toggle hits directly (no other change)."""
    return templates.TemplateResponse(request, "_list.html", _list_context(sort))


@router.get("/healthz")
def healthz():
    return {"status": "ok"}


def _list_fragment(request: Request, sort: str, error: str | None = None):
    return templates.TemplateResponse(request, "_list.html", _list_context(sort, error))


@router.post("/items")
def create_item(
    request: Request, name: str = Form(...), portions: int = Form(...), sort: str = SortParam
):
    try:
        with get_session() as session:
            services.add_item(session, name, portions)
    except services.ValidationError as exc:
        return _list_fragment(request, sort, error=str(exc))
    return _list_fragment(request, sort)


@router.post("/items/{item_id}/eat")
def eat_item(request: Request, item_id: int, portions: int = Form(...), sort: str = SortParam):
    try:
        with get_session() as session:
            services.eat(session, item_id, portions)
    except services.ValidationError as exc:
        return _list_fragment(request, sort, error=str(exc))
    return _list_fragment(request, sort)


@router.post("/items/{item_id}/add")
def add_to_item(request: Request, item_id: int, portions: int = Form(...), sort: str = SortParam):
    try:
        with get_session() as session:
            services.add_batch(session, item_id, portions)
    except services.ValidationError as exc:
        return _list_fragment(request, sort, error=str(exc))
    return _list_fragment(request, sort)


@router.post("/items/{item_id}/edit")
def edit_item(
    request: Request,
    item_id: int,
    name: str = Form(...),
    frozen_on: date = Form(...),
    sort: str = SortParam,
):
    try:
        with get_session() as session:
            services.edit_item(session, item_id, name, frozen_on)
    except services.ValidationError as exc:
        return _list_fragment(request, sort, error=str(exc))
    return _list_fragment(request, sort)


@router.post("/items/{item_id}/discard")
def discard_item(request: Request, item_id: int, sort: str = SortParam):
    try:
        with get_session() as session:
            services.discard(session, item_id)
    except services.ValidationError as exc:
        return _list_fragment(request, sort, error=str(exc))
    return _list_fragment(request, sort)
