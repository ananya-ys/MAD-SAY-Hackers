"""
app/services/wiki_service.py
Wiki: append-only Seen Case entries to error-type .md files.
Git-trackable markdown. No infra overhead.
LLM cannot overwrite existing sections — append-only invariant.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class WikiService:
    def __init__(self) -> None:
        self._wiki_dir = Path(settings.wiki_dir)
        self._wiki_dir.mkdir(parents=True, exist_ok=True)

    def get_context(self, error_type: str) -> str:
        """Return wiki page content for this error type. Empty string if no page."""
        page = self._wiki_dir / f"{error_type}.md"
        if page.exists():
            return page.read_text()[:2000]  # cap before LLM injection
        return ""

    def list_pages(self) -> list[dict]:
        pages = []
        for md in sorted(self._wiki_dir.glob("*.md")):
            content = md.read_text()
            seen_count = content.count("## Seen Case")
            pages.append({
                "slug": md.stem,
                "title": md.stem.replace("_", " "),
                "source_count": seen_count,
                "last_updated": datetime.fromtimestamp(md.stat().st_mtime).isoformat(),
            })
        return pages

    def get_page(self, slug: str) -> dict | None:
        page = self._wiki_dir / f"{slug}.md"
        if not page.exists():
            return None
        content = page.read_text()
        return {
            "slug": slug,
            "title": slug.replace("_", " "),
            "content": content,
            "source_count": content.count("## Seen Case"),
            "last_updated": datetime.fromtimestamp(page.stat().st_mtime).isoformat(),
        }

    def append_seen_case(
        self,
        *,
        error_type: str,
        root_cause: str,
        fix_description: str,
        source_layer: str,
        confidence: float,
        session_id: str,
    ) -> None:
        """
        Append a Seen Case entry. NEVER overwrites existing content.
        Called after every FIXED repair outcome.
        """
        page = self._wiki_dir / f"{error_type}.md"

        # Initialise page if new
        if not page.exists():
            page.write_text(
                f"# {error_type}\n\n"
                f"Auto-generated wiki page for `{error_type}`.\n\n"
                f"---\n\n"
            )

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        entry = (
            f"\n## Seen Case — {timestamp}\n\n"
            f"- **Source Layer:** {source_layer}\n"
            f"- **Root Cause:** {root_cause}\n"
            f"- **Fix:** {fix_description}\n"
            f"- **Confidence:** {confidence}\n"
            f"- **Session:** `{session_id}`\n\n"
            f"---\n"
        )

        with page.open("a") as f:
            f.write(entry)

        logger.info(
            "wiki_case_appended",
            error_type=error_type,
            source_layer=source_layer,
            session_id=session_id,
        )
