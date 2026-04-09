"""app/api/v1/wiki.py — Wiki read endpoints. Append-only writes handled by orchestrator."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.auth import CurrentUser, get_current_user
from app.services.wiki_service import WikiService

router = APIRouter(prefix="/wiki", tags=["wiki"])
_wiki = WikiService()


@router.get("")
async def list_wiki_pages(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    pages = _wiki.list_pages()
    return {"pages": pages, "total": len(pages)}


@router.get("/{slug}")
async def get_wiki_page(
    slug: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    # Sanitise slug — no path traversal
    if "/" in slug or ".." in slug:
        raise HTTPException(400, "Invalid slug")
    page = _wiki.get_page(slug)
    if not page:
        raise HTTPException(404, "Wiki page not found")
    return page
